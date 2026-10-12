import asyncio
import time
import logging
from datetime import timedelta, timezone
from sqlalchemy import select
from app.config import settings
from app.db import Session
from app.agents.workflows import graph, validate
from app.agents.tracing import node_trace
from app.integrations.clients import ProviderError
from pydantic import ValidationError
from app.models import (EngineeringEvent, WorkflowExecution, Project, PullRequestAnalysis, SprintSummary,
                        DetectedBlocker, TaskPriorityRecommendation, AuditLog, now)
from app.services.events import retry_delay
logger = logging.getLogger('sprintgraph.worker')
RESULTS = {'pull_request': PullRequestAnalysis, 'sprint_summary': SprintSummary, 'blockers': DetectedBlocker, 'priorities': TaskPriorityRecommendation}

async def process_once(*, delivery_prefix: str | None = None, event_id: int | None = None):
    with Session() as db:
        # One worker, database claims; SKIP LOCKED permits later multi-worker expansion.
        query = select(EngineeringEvent).where(
            EngineeringEvent.status.in_(['pending', 'retry']), EngineeringEvent.available_at <= now())
        if event_id is not None:
            query = query.where(EngineeringEvent.id == event_id)
        if delivery_prefix is not None:
            query = query.where(EngineeringEvent.source == 'evaluation',
                                EngineeringEvent.delivery_id.startswith(delivery_prefix, autoescape=True))
        event = db.scalar(query.order_by(EngineeringEvent.id).with_for_update(skip_locked=True).limit(1))
        if not event:
            return False
        event.status = 'running'
        event.started_at = now()
        event.attempts += 1
        execution = WorkflowExecution(event_id=event.id, workflow=event.event_type, status='running')
        db.add(execution)
        db.commit()
        start = time.perf_counter()
        project = db.get(Project, event.project_id)
        trace = []
        trace_token = node_trace.set(trace)
        try:
            state = await asyncio.wait_for(
                graph.ainvoke({'event_type': event.event_type, 'payload': event.payload, 'project': project}),
                timeout=settings().workflow_timeout_seconds)
            output = state['output']
            if event.event_type == 'blockers':
                analyses = db.scalars(select(PullRequestAnalysis).where(PullRequestAnalysis.project_id == project.id)).all()
                for item in output['items']:
                    item['pull_requests'] = sorted({a.data['evidence']['url'] for a in analyses if item['issue_key'] in a.data['evidence'].get('linked_issues', [])})
            output = validate({**state, 'output': output})['output']
            db.add(RESULTS[event.event_type](project_id=project.id, execution_id=execution.id,
                                           provider_id=output['provider_id'], data=output))
            event.status = execution.status = 'succeeded'
            event.completed_at = now()
            event.error = None
            execution.result = output
        except Exception as exc:
            logger.error('workflow_failure event_id=%s category=%s', event.id, type(exc).__name__)
            db.rollback()
            event = db.get(EngineeringEvent, event.id)
            execution = db.get(WorkflowExecution, execution.id)
            execution.status = 'failed'
            # Safe category only; never leak provider payloads or credentials.
            category = ('timeout' if isinstance(exc, TimeoutError) else
                        'provider' if isinstance(exc, ProviderError) else
                        'validation' if isinstance(exc, (ValidationError, ValueError)) else 'execution')
            event.error = execution.error = f'Workflow failed ({category}); inspect server diagnostics'
            retryable = not isinstance(exc, ProviderError) or exc.retryable
            event.status = 'retry' if retryable and event.attempts < settings().max_attempts else 'failed'
            delay = retry_delay(event.attempts)
            if isinstance(exc, ProviderError) and exc.retry_after is not None:
                delay = max(delay, timedelta(seconds=exc.retry_after))
            event.available_at = now() + delay
            if event.status == 'failed':
                event.completed_at = now()
        finally:
            node_trace.reset(trace_token)
        execution.duration_ms = (time.perf_counter() - start) * 1000
        db.add(AuditLog(organization_id=project.organization_id, action='workflow.' + execution.status,
                       details={'event_id': event.id, 'execution_id': execution.id, 'nodes': trace,
                                'integration_mode': settings().mode, 'llm_provider': settings().llm_provider,
                                'llm_inference_enabled': settings().llm_inference_enabled}))
        db.commit()
        return True

def recover():
    with Session() as db:
        stale = db.scalars(select(EngineeringEvent).where(EngineeringEvent.status == 'running', EngineeringEvent.started_at < now() - timedelta(minutes=10))).all()
        for event in stale:
            event.status = 'retry' if event.attempts < settings().max_attempts else 'failed'
            event.available_at = now()
            event.error = 'Worker interrupted'
            if event.status == 'failed':
                event.completed_at = now()
            for execution in db.scalars(select(WorkflowExecution).where(WorkflowExecution.event_id == event.id, WorkflowExecution.status == 'running')):
                execution.status = 'failed'
                execution.error = 'Worker interrupted'
                started = execution.created_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                execution.duration_ms = max(0, (now() - started).total_seconds() * 1000)
            project = db.get(Project, event.project_id)
            db.add(AuditLog(organization_id=project.organization_id, action='workflow.recovered',
                           details={'event_id': event.id, 'status': event.status, 'reason': 'worker_interrupted'}))
        db.commit()

async def run():
    while True:
        try:
            recover()
            if not await process_once():
                await asyncio.sleep(1)
        except Exception as exc:
            logger.error('worker_failure category=%s', type(exc).__name__)
            await asyncio.sleep(3)

if __name__ == '__main__':
    asyncio.run(run())
