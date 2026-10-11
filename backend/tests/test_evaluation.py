import asyncio
import pytest
from sqlalchemy import select
from app.config import settings
from app.evaluate import evaluate
from app.models import EngineeringEvent


def test_evaluation_only_processes_its_own_events(db):
    report = asyncio.run(evaluate(8))
    assert report['events'] == report['successful'] == 8
    assert report['failed'] == report['unfinished'] == 0
    assert report['execution_attempts'] == 8
    assert report['configuration']['llm_provider'] == 'demo'
    assert report['p95_end_to_end_ms'] >= report['p50_end_to_end_ms'] >= 0
    assert report['throughput_events_per_second'] > 0
    assert len(report['source_sha256']) == 4
    assert all(value['events'] == 2 for value in report['by_workflow'].values())
    db.expire_all()
    seed_events = db.scalars(select(EngineeringEvent).where(EngineeringEvent.source == 'demo')).all()
    assert len(seed_events) == 4
    assert all(event.status == 'pending' and event.attempts == 0 for event in seed_events)


@pytest.mark.parametrize('count', [0, -1, 10001])
def test_invalid_evaluation_size(count):
    with pytest.raises(ValueError, match='Event count'):
        asyncio.run(evaluate(count))


def test_evaluation_cannot_call_paid_provider(monkeypatch):
    monkeypatch.setattr(settings(), 'llm_provider', 'openai-compatible')
    with pytest.raises(ValueError, match='no live or paid'):
        asyncio.run(evaluate(4))
