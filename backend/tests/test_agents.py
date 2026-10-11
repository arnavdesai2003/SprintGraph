import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from app.agents.schemas import Analysis
from app.agents.workflows import graph, validate
from app.config import settings
from app.db import Session
from app.integrations.clients import Clients, ProviderError
from app.models import (Project, EngineeringEvent, WorkflowExecution, PullRequestAnalysis,
                        AuditLog, now)
from app.worker import process_once, recover


def invoke(db, workflow, payload=None):
    return asyncio.run(graph.ainvoke({'event_type': workflow, 'payload': payload or {'number': 42},
                                     'project': db.get(Project, 1)}))


@pytest.mark.parametrize('workflow', ['pull_request', 'sprint_summary', 'blockers', 'priorities'])
def test_only_the_selected_allowlisted_adapter_is_called(db, monkeypatch, workflow):
    client = Clients()
    pr = asyncio.run(client.pull_request('sprintgraph/demo', 42))
    sprint = asyncio.run(client.sprint(db.get(Project, 1)))
    fetch_pr = AsyncMock(return_value=pr)
    fetch_sprint = AsyncMock(return_value=sprint)
    monkeypatch.setattr(Clients, 'pull_request', fetch_pr)
    monkeypatch.setattr(Clients, 'sprint', fetch_sprint)
    state = invoke(db, workflow)
    assert isinstance(state['project'].id, int)
    assert fetch_pr.await_count == (1 if workflow == 'pull_request' else 0)
    assert fetch_sprint.await_count == (0 if workflow == 'pull_request' else 1)
    assert validate(state)['output'] == state['output']


@pytest.mark.parametrize('kind,payload', [
    ('execute_sql', {'number': 42}),
    ('pull_request', {'number': True}),
    ('pull_request', {'number': 42, 'command': 'merge'}),
    ('blockers', {'issue_key': 'OTHER-1'}),
    ('priorities', {'tool': 'shell'}),
])
def test_invalid_routing_inputs_never_reach_tools(db, monkeypatch, kind, payload):
    pr, sprint = AsyncMock(), AsyncMock()
    monkeypatch.setattr(Clients, 'pull_request', pr)
    monkeypatch.setattr(Clients, 'sprint', sprint)
    with pytest.raises((ValidationError, ValueError)):
        invoke(db, kind, payload)
    pr.assert_not_awaited()
    sprint.assert_not_awaited()


def test_mismatched_provider_pr_identity_is_rejected(db, monkeypatch):
    evidence = asyncio.run(Clients().pull_request('sprintgraph/demo', 999))
    monkeypatch.setattr(Clients, 'pull_request', AsyncMock(return_value=evidence))
    with pytest.raises(ValueError, match='identity'):
        invoke(db, 'pull_request')


def test_malformed_provider_evidence_is_rejected(db, monkeypatch):
    evidence = asyncio.run(Clients().pull_request('sprintgraph/demo', 42))
    evidence['files'][0]['additions'] = -1
    monkeypatch.setattr(Clients, 'pull_request', AsyncMock(return_value=evidence))
    with pytest.raises(ValidationError):
        invoke(db, 'pull_request')


def test_foreign_project_sprint_issue_is_rejected(db, monkeypatch):
    evidence = asyncio.run(Clients().sprint(db.get(Project, 1)))
    evidence['issues'][0]['key'] = 'OTHER-1'
    monkeypatch.setattr(Clients, 'sprint', AsyncMock(return_value=evidence))
    with pytest.raises(ValueError, match='configured project'):
        invoke(db, 'sprint_summary')


def test_duplicate_issue_keys_are_rejected(db, monkeypatch):
    evidence = asyncio.run(Clients().sprint(db.get(Project, 1)))
    evidence['issues'].append(deepcopy(evidence['issues'][0]))
    monkeypatch.setattr(Clients, 'sprint', AsyncMock(return_value=evidence))
    with pytest.raises(ValidationError, match='Duplicate Jira'):
        invoke(db, 'priorities')


@pytest.mark.parametrize('field,value', [('actions', [{'tool': 'merge'}]), ('sql', 'DROP TABLE users')])
def test_model_output_cannot_add_execution_fields(field, value):
    with pytest.raises(ValidationError):
        Analysis.model_validate({'summary': 'Advisory review', field: value})


def test_tampered_source_evidence_is_rejected(db):
    state = invoke(db, 'pull_request')
    state['output'] = deepcopy(state['output'])
    state['output']['evidence']['title'] = 'Changed after collection'
    with pytest.raises(ValueError, match='source evidence'):
        validate(state)


def test_tampered_result_identity_is_rejected(db):
    state = invoke(db, 'pull_request')
    state['output']['provider_id'] = 'other/repo#1'
    with pytest.raises(ValueError, match='provider identity'):
        validate(state)


def test_sprint_progress_must_match_source_counts(db):
    state = invoke(db, 'sprint_summary')
    state['output']['progress'] = 1
    with pytest.raises(ValueError, match='Sprint metrics'):
        validate(state)


def test_priority_score_tampering_is_rejected(db):
    state = invoke(db, 'priorities')
    state['output']['items'][0]['score'] += 1
    with pytest.raises(ValueError, match='business rules'):
        validate(state)


def test_priority_order_tampering_is_rejected(db):
    state = invoke(db, 'priorities')
    state['output']['items'].reverse()
    with pytest.raises(ValueError, match='business rules'):
        validate(state)


def test_potential_blocker_cannot_be_promoted_to_definite(db):
    state = invoke(db, 'blockers')
    potential = next(item for item in state['output']['items'] if item['certainty'] == 'potential')
    potential['certainty'] = 'definite'
    with pytest.raises(ValueError, match='source evidence'):
        validate(state)


def test_empty_sprint_produces_valid_zero_progress_and_empty_rankings(db, monkeypatch):
    monkeypatch.setattr(Clients, 'sprint', AsyncMock(return_value={'id': 'empty', 'name': 'Empty sprint', 'issues': []}))
    assert invoke(db, 'sprint_summary')['output']['progress'] == 0
    assert invoke(db, 'priorities')['output']['items'] == []
    assert invoke(db, 'blockers')['output']['items'] == []


def test_valid_zero_score_issue_has_an_explanation(db, monkeypatch):
    evidence = asyncio.run(Clients().sprint(db.get(Project, 1)))
    issue = evidence['issues'][-1]
    issue.update(priority='Lowest', severity=0, sprint=False)
    evidence['issues'] = [issue]
    monkeypatch.setattr(Clients, 'sprint', AsyncMock(return_value=evidence))
    ranked = invoke(db, 'priorities')['output']['items'][0]
    assert ranked['score'] == 0 and ranked['explanation']


def test_worker_timeout_persists_failure_and_no_partial_result(db, monkeypatch):
    async def stalled(*args, **kwargs):
        await asyncio.sleep(1)
    monkeypatch.setattr(graph, 'ainvoke', stalled)
    monkeypatch.setattr(settings(), 'workflow_timeout_seconds', .01)
    monkeypatch.setattr(settings(), 'max_attempts', 1)
    assert asyncio.run(process_once())
    db.expire_all()
    event = db.get(EngineeringEvent, 1)
    assert event.status == 'failed' and event.completed_at is not None
    assert '(timeout)' in event.error
    execution = db.scalar(select(WorkflowExecution).where(WorkflowExecution.event_id == 1))
    assert execution.status == 'failed' and execution.result is None and execution.duration_ms >= 0
    assert db.scalar(select(PullRequestAnalysis)) is None


def test_running_status_is_committed_before_provider_failure(db, monkeypatch):
    async def fail(state):
        with Session() as observed:
            assert observed.get(EngineeringEvent, 1).status == 'running'
            assert observed.scalar(select(WorkflowExecution).where(WorkflowExecution.event_id == 1)).status == 'running'
        raise ProviderError('private provider response')
    monkeypatch.setattr(graph, 'ainvoke', fail)
    assert asyncio.run(process_once())
    db.expire_all()
    event = db.get(EngineeringEvent, 1)
    assert event.status == 'retry' and '(provider)' in event.error
    assert 'private' not in event.error
    assert db.scalar(select(PullRequestAnalysis)) is None


def test_terminal_crash_recovery_has_completion_duration_and_audit(db):
    event = db.get(EngineeringEvent, 1)
    event.status = 'running'
    event.attempts = settings().max_attempts
    event.started_at = now() - timedelta(minutes=11)
    db.add(WorkflowExecution(event_id=1, workflow='pull_request', status='running',
                             created_at=now() - timedelta(minutes=11)))
    db.commit()
    recover()
    db.expire_all()
    assert db.get(EngineeringEvent, 1).status == 'failed'
    assert db.get(EngineeringEvent, 1).completed_at is not None
    execution = db.scalar(select(WorkflowExecution).where(WorkflowExecution.event_id == 1))
    assert execution.status == 'failed' and execution.duration_ms > 0
    assert db.scalar(select(AuditLog).where(AuditLog.action == 'workflow.recovered')) is not None
