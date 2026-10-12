from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models import EngineeringEvent


def test_dashboard_uses_evaluation_nearest_rank_metrics(client, headers, db):
    events = db.scalars(select(EngineeringEvent).order_by(EngineeringEvent.id)).all()
    start = datetime(2026, 10, 12, tzinfo=timezone.utc)
    for i, event in enumerate(events):
        event.created_at = start
        event.completed_at = start + timedelta(seconds=i + 1)
        event.status = 'failed' if i == 3 else 'succeeded'
        event.handling = 'manual' if i == 0 else 'automated'
        event.attempts = 3 if i == 3 else 1
    db.commit()
    response = client.get('/api/projects/1/overview', headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body['p50_latency_ms'] == 2000
    assert body['p95_latency_ms'] == 4000
    assert body['metrics']['latency_samples'] == 4
    assert body['metrics']['manually_handled'] == 1
    assert body['metrics']['execution_attempts'] == 6
    assert body['metrics']['successful_automation_fraction'] == .5
