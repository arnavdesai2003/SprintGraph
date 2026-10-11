"""Explicit event metrics shared by reproducible evaluation and tests."""
import math
from datetime import timezone


def percentile(values: list[float], quantile: float) -> float | None:
    """Nearest-rank percentile; callers may supply unsorted values."""
    if not 0 < quantile <= 1:
        raise ValueError('Quantile must be greater than zero and at most one')
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * quantile) - 1]


def summarize_events(events: list[dict]) -> dict:
    successful = sum(event['status'] == 'succeeded' for event in events)
    successful_automated = sum(event['status'] == 'succeeded' and event['handling'] == 'automated' for event in events)
    latencies = []
    workflows = {}
    for event in events:
        if event.get('completed_at') is not None:
            # SQLAlchemy SQLite reads UTC timestamps without tzinfo; PostgreSQL preserves it.
            start = event['created_at']
            finish = event['completed_at']
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if finish.tzinfo is None:
                finish = finish.replace(tzinfo=timezone.utc)
            duration = (finish - start).total_seconds() * 1000
            if duration < 0:
                raise ValueError('Completion precedes ingestion')
            latencies.append(duration)
        summary = workflows.setdefault(event['event_type'], {'events': 0, 'successful': 0, 'failed': 0})
        summary['events'] += 1
        summary['successful'] += event['status'] == 'succeeded'
        summary['failed'] += event['status'] == 'failed'
    return {
        'events': len(events),
        'successful': successful,
        'failed': sum(event['status'] == 'failed' for event in events),
        'unfinished': sum(event['status'] not in {'succeeded', 'failed'} for event in events),
        'automated': sum(event['handling'] == 'automated' for event in events),
        'manually_handled': sum(event['handling'] == 'manual' for event in events),
        'execution_attempts': sum(event['attempts'] for event in events),
        'successful_automation_fraction': successful_automated / len(events) if events else None,
        'latency_samples': len(latencies),
        'p50_end_to_end_ms': percentile(latencies, .5),
        'p95_end_to_end_ms': percentile(latencies, .95),
        'by_workflow': workflows,
    }
