import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import pytest
from sqlalchemy import event as sqlalchemy_event, func, select
from app.db import engine, Session
from app.models import AuditLog, EngineeringEvent, Project
from app.services.events import DuplicateDeliveryConflict, ingest


def signed_request(client, payload, delivery='phase2-delivery'):
    raw = json.dumps(payload).encode()
    signature = 'sha256=' + hmac.new(b'test-webhook-secret', raw, hashlib.sha256).hexdigest()
    return client.post('/api/webhooks/github', content=raw, headers={
        'content-type': 'application/json', 'x-github-event': 'pull_request',
        'x-github-delivery': delivery, 'x-hub-signature-256': signature})


def test_delivery_id_reuse_with_changed_content_is_conflict(client, db):
    payload = {'action': 'opened', 'number': 31, 'repository': {'full_name': 'sprintgraph/demo'}}
    assert signed_request(client, payload).status_code == 202
    changed = signed_request(client, {**payload, 'number': 32})
    assert changed.status_code == 409
    assert 'event_id' not in changed.json()
    assert db.scalar(select(func.count()).select_from(EngineeringEvent)) == 5
    assert db.scalar(select(func.count()).select_from(AuditLog)) == 5


def test_duplicate_delivery_cannot_disclose_another_projects_event(db):
    first = db.get(Project, 1)
    other = Project(organization_id=first.organization_id, name='Other project',
                    github_repository='sprintgraph/other', jira_key='OTHER')
    db.add(other)
    db.commit()
    ingest(db, first, 'github', 'same-id', 'pull_request', {'number': 1})
    with pytest.raises(DuplicateDeliveryConflict):
        ingest(db, other, 'github', 'same-id', 'pull_request', {'number': 1})


@pytest.mark.parametrize('payload', [
    {'action': 'opened', 'number': 1, 'repository': []},
    {'action': 'opened', 'number': True, 'repository': {'full_name': 'sprintgraph/demo'}},
    {'action': 'opened', 'number': 0, 'repository': {'full_name': 'sprintgraph/demo'}},
])
def test_signed_but_invalid_payloads_are_not_persisted(client, db, payload):
    assert signed_request(client, payload).status_code == 422
    assert db.scalar(select(func.count()).select_from(EngineeringEvent)) == 4


def test_oversized_webhook_is_rejected_before_persistence(client, db):
    response = client.post('/api/webhooks/github', content=b'x' * 1_000_001,
                           headers={'x-hub-signature-256': 'sha256=invalid'})
    assert response.status_code == 413
    assert db.scalar(select(func.count()).select_from(EngineeringEvent)) == 4


def test_missing_service_delivery_id_is_generated_before_lookup(db):
    project = db.get(Project, 1)
    first, created = ingest(db, project, 'manual', None, 'priorities', {})
    second, second_created = ingest(db, project, 'manual', None, 'priorities', {})
    assert created and second_created
    assert first.delivery_id and first.delivery_id != second.delivery_id


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires actual PostgreSQL concurrent writes')
def test_simultaneous_duplicate_inserts_create_one_event_and_audit():
    barrier = Barrier(2, timeout=10)
    counter_lock = Lock()
    first_reads = 0

    def synchronize_lookup(connection, cursor, statement, parameters, context, executemany):
        nonlocal first_reads
        if statement.lstrip().startswith('SELECT engineering_events.'):
            with counter_lock:
                first_reads += 1
                synchronize = first_reads <= 2
            if synchronize:
                # Both transactions observe an absent delivery before either inserts.
                barrier.wait()

    def submit():
        with Session() as db:
            return ingest(db, db.get(Project, 1), 'github', 'concurrent-delivery',
                          'pull_request', {'number': 99})

    sqlalchemy_event.listen(engine, 'after_cursor_execute', synchronize_lookup)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
    finally:
        sqlalchemy_event.remove(engine, 'after_cursor_execute', synchronize_lookup)
    assert results[0][0].id == results[1][0].id
    assert sorted(created for _, created in results) == [False, True]
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(EngineeringEvent).where(
            EngineeringEvent.delivery_id == 'concurrent-delivery')) == 1
        logs = db.scalars(select(AuditLog).where(AuditLog.action == 'event.ingested')).all()
        assert sum(log.details.get('delivery_id') == 'concurrent-delivery' for log in logs) == 1
