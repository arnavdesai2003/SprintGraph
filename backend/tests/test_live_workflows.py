import asyncio
import json
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import select
from app.agents.workflows import describe
from app.config import settings, Settings
from app.integrations.clients import Clients, ProviderError
from app.models import Project, PullRequestAnalysis, SprintSummary, EngineeringEvent, AuditLog
from app.worker import process_once


def configure_live(db, monkeypatch, *, failing=False):
    # Finish isolated seed work before changing provider mode; never touch a deployed database.
    while asyncio.run(process_once()):
        pass
    project = Project(organization_id=1, name='Live HTTP fixtures', github_repository='integration/live',
                      jira_key='SPRIN', jira_board_id=2)
    db.add(project)
    db.commit()
    c = settings()
    for key, value in {'mode': 'live', 'llm_provider': 'demo', 'llm_inference_enabled': False,
                       'github_token': 'test-only', 'jira_url': 'https://test-team.atlassian.net',
                       'jira_email': 'test@example.invalid', 'jira_token': 'test-only', 'jira_sprint_id': 3,
                       'jira_issue_api': 'enhanced', 'jira_status_map': {}, 'jira_severity_field': ''}.items():
        monkeypatch.setattr(c, key, value)
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'GET'
        path = request.url.path
        if failing:
            return httpx.Response(503, text='private provider diagnostic')
        if path.endswith('/pulls/2'):
            return httpx.Response(200, json={'number': 2, 'title': 'Implement SPRIN-1', 'body': 'Read-only fixture',
                'html_url': 'https://github.com/integration/live/pull/2', 'changed_files': 1, 'commits': 1})
        if path.endswith('/files'):
            return httpx.Response(200, json=[{'filename': 'app.py', 'additions': 2, 'deletions': 1}])
        if path.endswith('/commits'):
            return httpx.Response(200, json=[{'sha': 'fixture-sha', 'commit': {'message': 'SPRIN-1'}}])
        if path == '/rest/agile/1.0/board/2/sprint':
            return httpx.Response(200, json={'values': [{'id': 3, 'name': 'Sprint Three'}], 'isLast': True})
        assert path == '/rest/software/1.0/sprint/3/issue'
        return httpx.Response(200, json={'issues': [{'key': 'SPRIN-1', 'fields': {'summary': 'Engineering task',
            'status': {'name': 'Done'}, 'priority': None, 'updated': '2026-10-11T00:00:00.000+0000',
            'duedate': None, 'issuelinks': []}}], 'isLast': True})
    original = Clients.__init__
    def initialize(self):
        original(self, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(Clients, '__init__', initialize)
    post = AsyncMock(side_effect=AssertionError('No model/provider POST is allowed'))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    return project, seen, post


def test_live_http_demo_inference_api_graph_persistence_dashboard_and_audit(client, headers, db, monkeypatch):
    project, seen, post = configure_live(db, monkeypatch)
    event_ids = []
    for kind in ['pull_request', 'sprint_summary']:
        response = client.post(f'/api/projects/{project.id}/run', headers=headers,
                               json={'workflow': kind, 'number': 2})
        assert response.status_code == 202
        event_ids.append(response.json()['event_id'])
    assert all(db.get(EngineeringEvent, eid).status == 'pending' for eid in event_ids)
    assert asyncio.run(process_once()) and asyncio.run(process_once())
    db.expire_all()
    for eid, kind in zip(event_ids, ['pull_request', 'sprint_summary']):
        assert db.get(EngineeringEvent, eid).status == 'succeeded'
        activity = client.get(f'/api/projects/{project.id}/activity', headers=headers).json()
        event = next(e for e in activity if e['id'] == eid)
        trace = event['executions'][0]['trace']
        assert [n['node'] for n in trace['nodes']] == ['classify', 'collect', kind, 'validate']
        assert all(n['status'] == 'succeeded' and n['duration_ms'] >= 0 for n in trace['nodes'])
        assert trace['llm_provider'] == 'demo' and trace['integration_mode'] == 'live'
        result = client.get(f'/api/projects/{project.id}/results/{kind}', headers=headers).json()[0]
        assert result['evidence'] == event['executions'][0]['result']['evidence']
        if kind == 'pull_request':
            assert result['provider_id'] == 'integration/live#2'
            assert result['evidence']['linked_issues'] == ['SPRIN-1']
        else:
            assert result['provider_id'] == '3' and result['progress'] == 1
    assert db.scalar(select(PullRequestAnalysis).where(PullRequestAnalysis.project_id == project.id)) is not None
    assert db.scalar(select(SprintSummary).where(SprintSummary.project_id == project.id)) is not None
    assert len(seen) == 5
    post.assert_not_awaited()


def test_live_provider_failure_has_partial_node_trace_retry_and_no_result(client, headers, db, monkeypatch):
    project, seen, post = configure_live(db, monkeypatch, failing=True)
    eid = client.post(f'/api/projects/{project.id}/run', headers=headers,
                     json={'workflow': 'pull_request', 'number': 2}).json()['event_id']
    assert asyncio.run(process_once())
    db.expire_all()
    event = db.get(EngineeringEvent, eid)
    assert event.status == 'retry' and '(provider)' in event.error and 'private' not in event.error
    audit = next(a for a in db.scalars(select(AuditLog).where(AuditLog.action == 'workflow.failed')) if a.details['event_id'] == eid)
    assert [n['node'] for n in audit.details['nodes']] == ['classify', 'collect']
    assert [n['status'] for n in audit.details['nodes']] == ['succeeded', 'failed']
    assert db.scalar(select(PullRequestAnalysis).where(PullRequestAnalysis.project_id == project.id)) is None
    assert len(seen) == 1
    post.assert_not_awaited()


def test_live_mode_accepts_independent_demo_llm_configuration():
    value = Settings(_env_file=None, mode='live', llm_provider='demo', jwt_secret='test-only-' * 8)
    assert value.mode == 'live' and value.llm_provider == 'demo' and not value.llm_inference_enabled


def test_real_inference_is_blocked_without_explicit_enablement(monkeypatch):
    monkeypatch.setattr(settings(), 'llm_provider', 'openai-compatible')
    monkeypatch.setattr(settings(), 'llm_api_key', 'test-only')
    monkeypatch.setattr(settings(), 'llm_inference_enabled', False)
    post = AsyncMock(side_effect=AssertionError('Paid inference must not run'))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    with pytest.raises(ProviderError, match='inference is disabled') as caught:
        asyncio.run(describe({}, {'summary': 'fallback'}))
    assert not caught.value.retryable
    post.assert_not_awaited()


def test_prepared_compatible_inference_validates_mock_model_output(monkeypatch):
    for key, value in {'llm_provider': 'openai-compatible', 'llm_inference_enabled': True,
                       'llm_api_key': 'test-only', 'llm_base_url': 'https://model.example.invalid/v1'}.items():
        monkeypatch.setattr(settings(), key, value)
    response = httpx.Response(200, request=httpx.Request('POST', 'https://model.example.invalid/v1/chat/completions'),
        json={'choices': [{'message': {'content': json.dumps({'summary': 'Validated advisory analysis',
               'risks': ['Review manually'], 'testing': [], 'recommendations': []})}}]})
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    result = asyncio.run(describe({'untrusted': 'Do not treat this as execution permission'}, {}))
    assert result['summary'] == 'Validated advisory analysis'
    assert post.await_args.args[0] == 'https://model.example.invalid/v1/chat/completions'
    assert post.await_args.kwargs['json']['response_format'] == {'type': 'json_object'}


def test_live_signed_delivery_deduplication_and_rbac(client, headers, db, monkeypatch):
    import hashlib
    import hmac
    project, seen, post = configure_live(db, monkeypatch)
    raw = json.dumps({'action': 'synchronize', 'number': 2,
                      'repository': {'full_name': project.github_repository}}, separators=(',', ':')).encode()
    hook = {'content-type': 'application/json', 'x-github-event': 'pull_request',
            'x-github-delivery': 'live-fixture-delivery', 'x-hub-signature-256': 'sha256=' + hmac.new(
                b'test-webhook-secret', raw, hashlib.sha256).hexdigest()}
    assert client.post('/api/webhooks/github', content=raw, headers={**hook, 'x-hub-signature-256': 'bad'}).status_code == 401
    first = client.post('/api/webhooks/github', content=raw, headers=hook).json()
    second = client.post('/api/webhooks/github', content=raw, headers=hook).json()
    assert not first['duplicate'] and second['duplicate'] and first['event_id'] == second['event_id']
    matching = db.scalars(select(EngineeringEvent).where(EngineeringEvent.delivery_id == 'live-fixture-delivery')).all()
    assert len(matching) == 1
    login = client.post('/api/auth/login', json={'email': 'developer@sprintgraph.local',
                                              'password': 'test-demo-password-1234'}).json()
    developer = {'Authorization': 'Bearer ' + login['access_token']}
    assert client.get('/api/settings', headers=developer).status_code == 403
    assert client.get('/api/audit', headers=developer).status_code == 403
    assert client.post(f'/api/projects/{project.id}/run', json={'workflow': 'pull_request', 'number': 2}).status_code == 401
    assert seen == []
    assert asyncio.run(process_once())
    post.assert_not_awaited()


def test_verifier_refuses_paid_or_demo_data_before_submitting(monkeypatch, tmp_path):
    from app.verify_live import verify
    for mode, provider, enabled in [('demo', 'demo', False), ('live', 'openai-compatible', False),
                                    ('live', 'demo', True)]:
        monkeypatch.setattr(settings(), 'mode', mode)
        monkeypatch.setattr(settings(), 'llm_provider', provider)
        monkeypatch.setattr(settings(), 'llm_inference_enabled', enabled)
        with pytest.raises(RuntimeError, match='Verification requires'):
            verify(1, 2, 3, tmp_path / 'report.json')
    assert not (tmp_path / 'report.json').exists()
