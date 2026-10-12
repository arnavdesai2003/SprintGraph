import asyncio
from datetime import timedelta, timezone
from unittest.mock import AsyncMock
from sqlalchemy import select
from app.agents.workflows import graph
from app.integrations.clients import ProviderError
from app.models import EngineeringEvent, WorkflowExecution, PullRequestAnalysis, now
from app.worker import process_once


def test_rate_limit_delay_is_persisted_without_blocking_worker(db, monkeypatch):
    monkeypatch.setattr(graph, 'ainvoke', AsyncMock(side_effect=ProviderError('private', retry_after=120)))
    before = now()
    assert asyncio.run(process_once())
    db.expire_all()
    event = db.get(EngineeringEvent, 1)
    available = event.available_at
    if available.tzinfo is None:
        available = available.replace(tzinfo=timezone.utc)
    assert event.status == 'retry' and event.attempts == 1
    assert available >= before + timedelta(seconds=120)
    assert 'private' not in event.error
    # A delayed PR does not prevent the next queued workflow from being claimed.
    assert asyncio.run(process_once())
    db.expire_all()
    assert db.get(EngineeringEvent, 1).attempts == 1
    assert db.get(EngineeringEvent, 2).attempts == 1


def test_nonretryable_provider_error_finishes_on_first_attempt(db, monkeypatch):
    monkeypatch.setattr(graph, 'ainvoke', AsyncMock(side_effect=ProviderError('private', retryable=False)))
    assert asyncio.run(process_once())
    db.expire_all()
    event = db.get(EngineeringEvent, 1)
    assert event.status == 'failed' and event.attempts == 1 and event.completed_at is not None
    execution = db.scalar(select(WorkflowExecution).where(WorkflowExecution.event_id == 1))
    assert execution.status == 'failed' and execution.result is None
    assert db.scalar(select(PullRequestAnalysis)) is None


def test_short_provider_delay_does_not_reduce_exponential_backoff(db, monkeypatch):
    monkeypatch.setattr(graph, 'ainvoke', AsyncMock(side_effect=ProviderError('rate limited', retry_after=0)))
    before = now()
    assert asyncio.run(process_once())
    db.expire_all()
    event = db.get(EngineeringEvent, 1)
    available = event.available_at
    if available.tzinfo is None:
        available = available.replace(tzinfo=timezone.utc)
    assert event.status == 'retry' and available >= before + timedelta(seconds=2)
