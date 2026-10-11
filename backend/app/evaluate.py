"""Reproducible demo workload. Never reports production productivity savings."""
import argparse
import asyncio
import hashlib
import json
import platform
import time
import uuid
from datetime import date
from pathlib import Path
from sqlalchemy import select
from app.config import settings
from app.db import Session
from app.models import EngineeringEvent, Project
from app.services.events import ingest
from app.services.metrics import summarize_events
from app.worker import process_once


async def evaluate(count: int) -> dict:
    if not 1 <= count <= 10000:
        raise ValueError('Event count must be between 1 and 10000')
    config = settings()
    if config.mode != 'demo' or config.llm_provider != 'demo':
        raise ValueError('Evaluation requires demo mode and demo LLM provider; no live or paid calls are allowed')
    batch = 'evaluation-' + str(uuid.uuid4())
    started = time.perf_counter()
    ids = []
    with Session() as db:
        project = db.scalar(select(Project).where(Project.github_repository == 'sprintgraph/demo'))
        if not project:
            raise ValueError('Seed demo data first')
        for index in range(count):
            workflow = ['pull_request', 'sprint_summary', 'blockers', 'priorities'][index % 4]
            event, _ = ingest(db, project, 'evaluation', f'{batch}-{index}', workflow, {'number': index + 1})
            ids.append(event.id)
    deadline = asyncio.get_running_loop().time() + max(60, count * 2)
    while True:
        # Never consume an unrelated pending webhook/manual event during evaluation.
        processed = await process_once(delivery_prefix=batch + '-')
        with Session() as db:
            events = db.scalars(select(EngineeringEvent).where(EngineeringEvent.id.in_(ids))).all()
            if len(events) != count:
                raise RuntimeError('Evaluation event set changed during the run')
            if all(event.status in {'succeeded', 'failed'} for event in events):
                break
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError('Evaluation did not complete within its bounded deadline')
        await asyncio.sleep(0 if processed else .05)
    elapsed = time.perf_counter() - started
    metrics = summarize_events([
        {'status': event.status, 'handling': event.handling, 'attempts': event.attempts,
         'event_type': event.event_type, 'created_at': event.created_at, 'completed_at': event.completed_at}
        for event in events
    ])
    source_hashes = {
        name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in ['integrations/clients.py', 'agents/workflows.py', 'services/scoring.py', 'worker.py']
    }
    return {
        'dataset': 'synthetic-demo-v1', 'run_id': batch,
        'fixture_reference_date': date.today().isoformat(), 'source_sha256': source_hashes,
        'runtime': {'python': platform.python_version(), 'platform': platform.system(),
                    'architecture': platform.machine()},
        'configuration': {'mode': config.mode, 'llm_provider': config.llm_provider,
                          'priority_weights': config.priority_weights, 'stalled_days': config.stalled_days,
                          'max_attempts': config.max_attempts},
        **metrics,
        'wall_duration_seconds': elapsed,
        'throughput_events_per_second': len(events) / elapsed if elapsed > 0 else None,
        'definitions': {
            'latency': 'created_at to completed_at; includes queueing and retries; includes successes and failures',
            'percentiles': 'nearest rank, ceil(n * quantile), of terminal-event latencies',
            'throughput': 'all terminal events / wall time from enqueue start through completion',
            'successful_automation_fraction': 'successful automated events / all events in this synthetic run',
            'handling': 'all demo fixtures use automated handling; no manual baseline is simulated',
        },
        'disclaimer': 'Synthetic demonstration using deterministic mock LLM. Does not verify historical 41% automation across 537+ events.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=int, default=100)
    parser.add_argument('--output', default='evaluation-report.json')
    args = parser.parse_args()
    if not 1 <= args.events <= 10000:
        parser.error('--events must be between 1 and 10000')
    report = asyncio.run(evaluate(args.events))
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if report['failed'] or report['unfinished']:
        raise SystemExit(1)
