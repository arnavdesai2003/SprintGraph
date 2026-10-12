import asyncio
from app.models import EngineeringEvent
from app.services.events import ingest
from app.models import Project
from app.worker import process_once


def test_targeted_worker_does_not_claim_other_pending_events(db):
    project = db.get(Project, 1)
    first, _ = ingest(db, project, 'manual', 'target-filter-first', 'pull_request', {'number': 42})
    target, _ = ingest(db, project, 'manual', 'target-filter-second', 'pull_request', {'number': 42})
    assert asyncio.run(process_once(event_id=target.id))
    db.expire_all()
    assert db.get(EngineeringEvent, first.id).status == 'pending'
    assert db.get(EngineeringEvent, target.id).status == 'succeeded'
    assert not asyncio.run(process_once(event_id=target.id))
