"""Trusted local operator: one PR event, one Gemini attempt, no automatic retry.

Stop the ordinary worker first. The exclusive report file prevents accidental reruns.
"""
import argparse
import asyncio
import json
from pathlib import Path
from unittest.mock import patch
import httpx
from sqlalchemy import select
from app.agents.inference import configuration
from app.config import settings
from app.db import Session, engine
from app.models import EngineeringEvent, WorkflowExecution, PullRequestAnalysis, AuditLog
from app.verify_live import verification_session
from app.worker import process_once
from app.integrations.clients import ProviderError


class AcceptanceError(RuntimeError):
    """Only fixed operator-safe messages, never provider exceptions."""


def diagnose(report_path):
    """Read configuration, queue counts and report metadata; never submit work."""
    c = settings()
    result = {'mode': c.mode, 'provider': c.llm_provider, 'model': c.llm_model,
              'inference_enabled': c.llm_inference_enabled,
              'api_key_present': bool(c.llm_api_key.strip()),
              'database_dialect': engine.dialect.name, 'network_requests': 0,
              'report_exists': report_path.exists()}
    try:
        configuration(c)
        result['configuration_valid'] = True
    except ProviderError:
        result['configuration_valid'] = False
    if report_path.exists():
        try:
            existing = json.loads(report_path.read_text())
            result['previous_report'] = {k: existing.get(k) for k in
                ['status', 'event_id', 'inference_requests', 'event_status', 'result_id']}
        except (ValueError, OSError):
            result['previous_report'] = 'Unreadable; do not delete or rerun blindly'
    with Session() as db:
        result['running_event_ids'] = list(db.scalars(select(EngineeringEvent.id).where(
            EngineeringEvent.status == 'running')))
    print(json.dumps(result, indent=2))


def verify(project_id, number, report_path):
    c = settings()
    config = configuration(c)
    if (c.mode != 'live' or not c.llm_inference_enabled or not config['gemini']
            or c.llm_model != 'gemini-3.1-flash-lite' or engine.dialect.name != 'postgresql'):
        raise AcceptanceError('Requires live PostgreSQL, enabled Gemini compatibility endpoint and gemini-3.1-flash-lite; run --diagnose')
    report = {'status': 'started', 'project_id': project_id, 'pr_number': number, 'model': c.llm_model,
              'inference_requests': 0, 'event_id': None}
    # Refuse to silently repeat a potentially completed provider request.
    with report_path.open('x') as handle:
        json.dump(report, handle)
    event_id = None
    previous_attempts = c.max_attempts
    original_post = httpx.AsyncClient.post

    async def single_post(client, url, *args, **kwargs):
        if str(url) != config['endpoint'] or report['inference_requests'] != 0:
            raise AcceptanceError('One-shot inference permits one request to the configured Gemini endpoint')
        report['inference_requests'] += 1
        report_path.write_text(json.dumps(report, indent=2))
        return await original_post(client, url, *args, **kwargs)

    try:
        with Session() as db:
            if db.scalar(select(EngineeringEvent.id).where(EngineeringEvent.status == 'running')):
                raise AcceptanceError('A workflow is running; stop worker and wait before acceptance')
        headers = {'Authorization': 'Bearer ' + verification_session(project_id)}
        with httpx.Client(base_url='http://localhost:8000/api/', headers=headers, timeout=15) as api:
            response = api.get('settings')
            if response.status_code != 200:
                raise AcceptanceError('Authenticated API settings unavailable')
            current = response.json()
            if (current['mode'] != 'live' or current['llm_provider'] != 'openai-compatible'
                    or not current.get('llm_inference_enabled')):
                raise AcceptanceError('Recreate backend with enabled compatible configuration first')
            response = api.post(f'projects/{project_id}/run', json={'workflow': 'pull_request', 'number': number})
            if response.status_code != 202:
                raise AcceptanceError('Authenticated PR event submission rejected')
            event_id = report['event_id'] = response.json()['event_id']
            report_path.write_text(json.dumps(report, indent=2))
            c.max_attempts = 1
            with patch('httpx.AsyncClient.post', single_post):
                if not asyncio.run(process_once(event_id=event_id)):
                    raise AcceptanceError('Event was claimed elsewhere; ordinary worker must be stopped')
            with Session() as db:
                event = db.get(EngineeringEvent, event_id)
                execution = db.scalar(select(WorkflowExecution).where(WorkflowExecution.event_id == event_id))
                report['event_status'] = event.status
                if event.status != 'succeeded' or event.attempts != 1 or report['inference_requests'] != 1:
                    raise AcceptanceError('One-shot workflow failed; inspect Workflow Activity; do not automatically rerun')
                result = db.scalar(select(PullRequestAnalysis).where(PullRequestAnalysis.execution_id == execution.id))
                audit = next((a for a in db.scalars(select(AuditLog).where(AuditLog.action == 'workflow.succeeded'))
                              if a.details.get('execution_id') == execution.id), None)
                expected = ['classify', 'collect', 'pull_request', 'validate']
                if (result is None or result.data != execution.result or audit is None
                        or [n['node'] for n in audit.details['nodes']] != expected
                        or any(n['status'] != 'succeeded' for n in audit.details['nodes'])):
                    raise AcceptanceError('Persistence or observed graph trace verification failed')
                report['nodes'] = audit.details['nodes']
                report['execution_id'] = execution.id
                report['result_id'] = result.id
                saved = result.data
            response = api.get(f'projects/{project_id}/results/pull_request')
            if response.status_code != 200 or not any(
                    r.get('id') == report['result_id'] and r.get('analysis') == saved['analysis']
                    for r in response.json()):
                raise AcceptanceError('Dashboard API did not return the persisted analysis')
            report['status'] = 'passed'
            print('PASS: One Gemini request; PR graph succeeded; PostgreSQL result, audit and dashboard API verified')
    except Exception as exc:
        report['status'] = 'failed'
        report['failure'] = str(exc) if isinstance(exc, AcceptanceError) else 'Unexpected failure; inspect safe workflow status'
        print('FAIL: One-shot acceptance incomplete; inspect safe event status and local report. No automatic rerun.')
        raise AcceptanceError(report['failure']) from None
    finally:
        c.max_attempts = previous_attempts
        report_path.write_text(json.dumps(report, indent=2))
        print('Report:', report_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--pr-number', type=int, required=True)
    parser.add_argument('--report', type=Path, default=Path('/tmp/sprintgraph-gemini-once.json'))
    parser.add_argument('--diagnose', action='store_true', help='Read-only local diagnostics; no inference or event submission')
    args = parser.parse_args()
    if min(args.project_id, args.pr_number) < 1:
        parser.error('IDs must be positive')
    try:
        if args.diagnose:
            diagnose(args.report)
            return
        verify(args.project_id, args.pr_number, args.report)
    except FileExistsError:
        parser.exit(1, 'Verification stopped: one-shot report already exists. Run --diagnose; do not delete it or resubmit until prior request count is checked.\n')
    except AcceptanceError as exc:
        parser.exit(1, f'Verification stopped: {exc}. Keep ordinary worker stopped.\n')
    except ProviderError:
        parser.exit(1, 'Verification stopped: invalid model configuration; run app.agents.check and --diagnose.\n')
    except Exception:
        parser.exit(1, 'Verification stopped: unexpected configuration or infrastructure failure; run --diagnose.\n')


if __name__ == '__main__':
    main()
