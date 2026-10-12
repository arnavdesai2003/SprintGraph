import asyncio
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import select
from pydantic import ValidationError
from app.agents.workflows import graph, describe
from app.config import settings
from app.integrations.clients import Clients, ProviderError
from app.models import (EngineeringEvent, Project, PullRequestAnalysis, SprintSummary, DetectedBlocker,
                        TaskPriorityRecommendation, Organization, now)
from app.services.events import ingest
from app.worker import process_once, recover

def drain():
    async def run():
        while await process_once():
            pass
    asyncio.run(run())

def test_health_and_auth(client, headers):
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/ready').status_code == 200
    assert client.get('/api/projects').status_code == 401
    assert client.get('/api/auth/me', headers=headers).json()['role'] == 'admin'
    assert client.post('/api/auth/login', json={'email': 'nobody', 'password': 'wrong'}).status_code == 401
    assert client.get('/api/projects', headers={'Authorization': 'Bearer invalid'}).status_code == 401

def test_rbac(client, headers):
    login = client.post('/api/auth/login', json={'email': 'developer@sprintgraph.local', 'password': 'test-demo-password-1234'}).json()
    developer = {'Authorization': 'Bearer ' + login['access_token']}
    assert client.get('/api/settings', headers=developer).status_code == 403
    assert client.patch('/api/users/1/role', headers=developer, json={'role': 'developer', 'confirmed': True}).status_code == 403
    assert client.get('/api/projects/1/overview', headers=developer).status_code == 200
    assert client.patch('/api/users/2/role', headers=headers, json={'role': 'admin'}).status_code == 422
    assert client.patch('/api/users/2/role', headers=headers, json={'role': 'admin', 'confirmed': True}).status_code == 200
    assert any(a['action'] == 'user.role_changed' for a in client.get('/api/audit', headers=headers).json())

def test_organization_isolation(client, headers, db):
    org = Organization(name='Other team')
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name='Private', github_repository='other/private', jira_key='PRIVATE')
    db.add(project)
    db.commit()
    for path in ['overview', 'activity', 'results/pull_request']:
        assert client.get(f'/api/projects/{project.id}/{path}', headers=headers).status_code == 404
    assert client.post(f'/api/projects/{project.id}/run', headers=headers, json={'workflow': 'blockers'}).status_code == 404

def signature(body):
    return 'sha256=' + hmac.new(b'test-webhook-secret', body, hashlib.sha256).hexdigest()

def test_github_signature_duplicate_and_end_to_end(client, headers, db):
    raw = json.dumps({'action': 'opened', 'number': 77, 'repository': {'full_name': 'sprintgraph/demo'}}).encode()
    webhook_headers = {'x-github-event': 'pull_request', 'x-github-delivery': 'delivery-77', 'x-hub-signature-256': signature(raw), 'content-type': 'application/json'}
    assert client.post('/api/webhooks/github', content=raw, headers={**webhook_headers, 'x-hub-signature-256': 'sha256=bad'}).status_code == 401
    response = client.post('/api/webhooks/github', content=raw, headers=webhook_headers)
    assert response.status_code == 202 and not response.json()['duplicate']
    second = client.post('/api/webhooks/github', content=raw, headers=webhook_headers)
    assert second.json()['duplicate'] and second.json()['event_id'] == response.json()['event_id']
    drain()
    results = client.get('/api/projects/1/results/pull_request', headers=headers).json()
    assert any(r['evidence']['number'] == 77 for r in results)
    assert db.scalar(select(EngineeringEvent).where(EngineeringEvent.delivery_id == 'delivery-77')).status == 'succeeded'

def test_all_demo_workflows(client, headers, db):
    drain()
    for table in [PullRequestAnalysis, SprintSummary, DetectedBlocker, TaskPriorityRecommendation]:
        assert db.scalar(select(table)) is not None
    overview = client.get('/api/projects/1/overview', headers=headers).json()
    assert overview['total_events'] == 4
    assert overview['statuses']['succeeded'] == 4
    assert overview['p95_latency_ms'] >= 0
    assert len(client.get('/api/audit', headers=headers).json()) >= 8
    assert client.get('/api/projects/1/results/sprint_summary', headers=headers).json()[0]['progress'] == .25

def test_manual_run_and_validation(client, headers):
    assert client.post('/api/projects/1/run', headers=headers, json={'workflow': 'shell'}).status_code == 422
    assert client.post('/api/projects/1/run', headers=headers, json={'workflow': 'pull_request', 'number': -1}).status_code == 422
    assert client.post('/api/projects/1/run', headers=headers, json={'workflow': 'priorities'}).status_code == 202

def test_jira_verified_ingestion(client):
    body = {'issue': {'key': 'SG-102'}}
    assert client.post('/api/webhooks/jira/1', json=body).status_code == 401
    headers = {'authorization': 'Bearer test-jira-secret', 'x-delivery-id': 'jira-1'}
    assert client.post('/api/webhooks/jira/1', json=body, headers=headers).status_code == 202
    assert client.post('/api/webhooks/jira/1', json=body, headers=headers).json()['duplicate']
    assert client.post('/api/webhooks/jira/1', json={'issue': {'key': 'OTHER-1'}}, headers=headers).status_code == 422

@pytest.mark.parametrize('workflow', ['pull_request', 'sprint_summary', 'blockers', 'priorities'])
def test_graph_routing(workflow, db):
    project = db.get(Project, 1)
    state = asyncio.run(graph.ainvoke({'event_type': workflow, 'payload': {'number': 42}, 'project': project}))
    assert 'evidence' in state['output']
    assert state['output']['provider_id']

def test_invalid_graph_route(db):
    with pytest.raises(ValidationError):
        asyncio.run(graph.ainvoke({'event_type': 'arbitrary_command', 'payload': {}, 'project': db.get(Project, 1)}))

def test_bounded_retry(monkeypatch, db):
    monkeypatch.setattr(Clients, 'pull_request', AsyncMock(side_effect=ProviderError('unavailable')))
    for attempt in range(1, 4):
        asyncio.run(process_once())
        db.expire_all()
        event = db.get(EngineeringEvent, 1)
        assert event.attempts == attempt
        assert event.status == ('failed' if attempt == 3 else 'retry')
        assert 'unavailable' not in event.error
        event.available_at = now() - timedelta(seconds=1)
        db.commit()
    assert db.scalar(select(PullRequestAnalysis)) is None

def test_recovery(db):
    event = db.get(EngineeringEvent, 1)
    event.status = 'running'
    event.started_at = now() - timedelta(minutes=11)
    db.commit()
    recover()
    db.expire_all()
    assert db.get(EngineeringEvent, 1).status == 'retry'

def test_idempotent_ingest(db):
    project = db.get(Project, 1)
    first, created = ingest(db, project, 'github', 'unique', 'pull_request', {'number': 1})
    second, duplicate = ingest(db, project, 'github', 'unique', 'pull_request', {'number': 1})
    assert created and not duplicate and first.id == second.id

def test_provider_failure_is_safe(monkeypatch):
    async def fail(*args, **kwargs):
        raise httpx.ConnectError('secret must not leak')
    monkeypatch.setattr(httpx.AsyncClient, 'get', fail)
    with pytest.raises(ProviderError, match='transport') as exc:
        asyncio.run(Clients().request('https://api.github.com'))
    assert 'secret' not in str(exc.value)

def test_failed_ai_request(monkeypatch):
    monkeypatch.setattr(settings(), 'llm_provider', 'openai-compatible')
    monkeypatch.setattr(settings(), 'llm_inference_enabled', True)
    monkeypatch.setattr(settings(), 'llm_api_key', 'unit-test-only')
    async def fail(*args, **kwargs):
        raise httpx.ConnectError('private')
    monkeypatch.setattr(httpx.AsyncClient, 'post', fail)
    with pytest.raises(ProviderError, match='LLM connection failed; retry later') as exc:
        asyncio.run(describe({}, {'summary': 'test'}))
    assert exc.value.retryable
    assert 'private' not in str(exc.value)
    assert 'unit-test-only' not in str(exc.value)

def test_invalid_ai_output(monkeypatch):
    monkeypatch.setattr(settings(), 'llm_provider', 'openai-compatible')
    monkeypatch.setattr(settings(), 'llm_inference_enabled', True)
    monkeypatch.setattr(settings(), 'llm_api_key', 'unit-test-only')
    async def invalid(*args, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', 'https://example.invalid'), json={'choices': [{'message': {'content': '{"summary": 42}'}}]})
    monkeypatch.setattr(httpx.AsyncClient, 'post', invalid)
    with pytest.raises(ProviderError):
        asyncio.run(describe({}, {'summary': 'test'}))

def test_settings_redacts_secrets(client, headers):
    result = client.get('/api/settings', headers=headers).text
    assert 'test-webhook-secret' not in result
    assert 'test-demo-password' not in result

def test_missing_webhook_secret(client, monkeypatch):
    monkeypatch.setattr(settings(), 'github_webhook_secret', '')
    assert client.post('/api/webhooks/github', json={}).status_code == 503
