"""Trusted local operator verification: real provider reads, deterministic demo inference."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import time
import uuid
import httpx
import jwt
from sqlalchemy import select
from app.config import settings
from app.db import Session, engine
from app.models import (Project, User, EngineeringEvent, WorkflowExecution,
                        PullRequestAnalysis, SprintSummary, AuditLog)


def verification_session(project_id):
    with Session() as db:
        project = db.get(Project, project_id)
        if project is None:
            raise RuntimeError('Project does not exist')
        user = db.scalar(select(User).where(User.organization_id == project.organization_id,
                                           User.role == 'admin').order_by(User.id))
        if user is None:
            raise RuntimeError('Project organization has no administrator')
        return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
                          settings().jwt_secret, algorithm='HS256')


def verify(project_id, number, sprint_id, report_path, *, timeout=180):
    c = settings()
    if c.mode != 'live' or c.llm_provider != 'demo' or c.llm_inference_enabled:
        raise RuntimeError('Verification requires MODE=live, LLM_PROVIDER=demo, LLM_INFERENCE_ENABLED=false')
    if engine.dialect.name != 'postgresql':
        raise RuntimeError('Real workflow acceptance requires PostgreSQL')
    bearer = verification_session(project_id)
    with Session() as db:
        project = db.get(Project, project_id)
        identity = {'repository': project.github_repository, 'jira_key': project.jira_key,
                    'board_id': project.jira_board_id, 'sprint_id': sprint_id, 'pr_number': number}
        developer = db.scalar(select(User).where(User.role == 'developer').order_by(User.id))
        developer_session = None
        if developer:
            developer_session = jwt.encode({'sub': str(developer.id),
                'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}, c.jwt_secret, algorithm='HS256')
            developer_org = developer.organization_id
        else:
            developer_org = None
    checks = []
    report = {'status': 'incomplete', 'started_at': datetime.now(timezone.utc).isoformat(),
              'project_id': project_id, 'resources': identity,
              'integration_mode': 'live', 'llm_provider': 'demo', 'paid_inference_enabled': False,
              'checks': checks, 'events': [], 'limitations': ['Browser display requires the separate browser check.']}

    def passed(label):
        checks.append(label)
        print('PASS:', label, flush=True)

    try:
        with httpx.Client(base_url='http://localhost:8000/api/', timeout=15) as http:
            def request(path, *, method='GET', body=None, credential=bearer, headers=None, expected=200):
                merged = dict(headers or {})
                if credential:
                    merged['Authorization'] = 'Bearer ' + credential
                response = http.request(method, path, json=body, headers=merged)
                if response.status_code != expected:
                    raise RuntimeError(f'{method} {path}: expected {expected}, received {response.status_code}')
                return response.json()

            config = request('settings')
            if config['mode'] != 'live' or config['llm_provider'] != 'demo' or config.get('llm_inference_enabled', True):
                raise RuntimeError('Running API configuration differs; recreate backend and worker first')
            passed('Running API uses live integrations and demo inference with paid inference disabled')
            request('projects', credential='', expected=401)
            request(f'projects/{project_id}/run', method='POST', credential='', body={'workflow': 'pull_request', 'number': number}, expected=401)
            if developer_session:
                request('settings', credential=developer_session, expected=403)
                request('audit', credential=developer_session, expected=403)
                if developer_org != project.organization_id:
                    for endpoint in ['activity', 'results/pull_request']:
                        request(f'projects/{project_id}/{endpoint}', credential=developer_session, expected=404)
                    request(f'projects/{project_id}/run', method='POST', credential=developer_session,
                            body={'workflow': 'pull_request', 'number': number}, expected=404)
                passed('Anonymous access, developer admin restrictions and available organization boundaries enforced')
            else:
                passed('Anonymous read and workflow submission rejected')
                report['limitations'].append('No existing Developer account; live Developer checks skipped (covered by automated tests).')
            prefix = f'projects/{project_id}'
            events = {}
            for kind in ['pull_request', 'sprint_summary']:
                result = request(prefix + '/run', method='POST', body={'workflow': kind, 'number': number}, expected=202)
                events[result['event_id']] = kind
            passed('Authenticated API queued PR analysis and sprint summary')
            if not c.github_webhook_secret:
                raise RuntimeError('GitHub webhook signing secret is required for deduplication verification')
            payload = {'action': 'synchronize', 'number': number, 'repository': {'full_name': project.github_repository}}
            # httpx emits compact JSON; sign those exact bytes and send the same bytes.
            raw = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
            delivery = 'live-verification-' + str(uuid.uuid4())
            headers = {'Content-Type': 'application/json', 'X-GitHub-Event': 'pull_request',
                       'X-GitHub-Delivery': delivery, 'X-Hub-Signature-256': 'sha256=' + hmac.new(
                           c.github_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()}
            def webhook(signature):
                response = http.post('webhooks/github', content=raw,
                                     headers={**headers, 'X-Hub-Signature-256': signature})
                return response
            if webhook('sha256=invalid').status_code != 401:
                raise RuntimeError('Unsigned webhook was accepted')
            first, duplicate = webhook(headers['X-Hub-Signature-256']), webhook(headers['X-Hub-Signature-256'])
            if first.status_code != 202 or duplicate.status_code != 202:
                raise RuntimeError('Signed webhook submission failed')
            a, b = first.json(), duplicate.json()
            if a['duplicate'] or not b['duplicate'] or a['event_id'] != b['event_id']:
                raise RuntimeError('Webhook deduplication failed')
            events[a['event_id']] = 'pull_request'
            passed('Webhook signature rejection and duplicate delivery protection passed')
            report['events'] = [{'event_id': eid, 'workflow': kind} for eid, kind in events.items()]
            deadline = time.monotonic() + timeout
            previous = None
            while True:
                activity = {e['id']: e for e in request(prefix + '/activity')}
                snapshot = {eid: activity.get(eid, {}).get('status', 'missing') for eid in events}
                for entry in report['events']:
                    observed = activity.get(entry['event_id'], {})
                    entry.update(status=observed.get('status', 'missing'), attempts=observed.get('attempts', 0),
                                 execution_traces=[x.get('trace') for x in observed.get('executions', [])])
                if snapshot != previous:
                    print('WAIT:', json.dumps(snapshot), flush=True)
                    previous = snapshot
                if any(status == 'failed' for status in snapshot.values()):
                    raise RuntimeError('A workflow failed; inspect its activity trace and worker logs')
                if all(status == 'succeeded' for status in snapshot.values()):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Workflow timeout; submitted events remain stored (no cleanup/reset performed)')
                time.sleep(1)
            api_audits = request('audit')
            with Session() as db:
                for entry in report['events']:
                    eid, kind = entry['event_id'], entry['workflow']
                    event = db.get(EngineeringEvent, eid)
                    executions = db.scalars(select(WorkflowExecution).where(WorkflowExecution.event_id == eid)).all()
                    execution = next((x for x in executions if x.status == 'succeeded'), None)
                    if event.status != 'succeeded' or not event.completed_at or not execution or execution.duration_ms is None:
                        raise RuntimeError(f'Event {eid}: incomplete persisted status/duration')
                    model = PullRequestAnalysis if kind == 'pull_request' else SprintSummary
                    saved = db.scalar(select(model).where(model.execution_id == execution.id, model.project_id == project_id))
                    if saved is None or saved.data != execution.result:
                        raise RuntimeError(f'Event {eid}: missing or mismatched result table')
                    expected_id = f'{project.github_repository}#{number}' if kind == 'pull_request' else str(sprint_id)
                    if saved.provider_id != expected_id:
                        raise RuntimeError(f'Event {eid}: provider identity does not match requested resource')
                    audit = db.scalar(select(AuditLog).where(AuditLog.organization_id == project.organization_id,
                        AuditLog.action == 'workflow.succeeded').order_by(AuditLog.id.desc()).filter(
                            AuditLog.details['execution_id'].as_integer() == execution.id))
                    if not any(audit_row['action'] == 'workflow.succeeded' and
                               audit_row['details'].get('execution_id') == execution.id for audit_row in api_audits):
                        raise RuntimeError(f'Event {eid}: audit API record missing')
                    expected_nodes = ['classify', 'collect', kind, 'validate']
                    if not audit or [n['node'] for n in audit.details.get('nodes', [])] != expected_nodes:
                        raise RuntimeError(f'Event {eid}: actual node execution audit missing')
                    if (any(n['status'] != 'succeeded' for n in audit.details['nodes'])
                            or audit.details['integration_mode'] != 'live' or audit.details['llm_provider'] != 'demo'
                            or audit.details['llm_inference_enabled']):
                        raise RuntimeError(f'Event {eid}: worker configuration or node status mismatch')
                    api_execution = next(x for x in activity[eid]['executions'] if x['id'] == execution.id)
                    if api_execution['trace'] != audit.details or api_execution['result'] != saved.data:
                        raise RuntimeError(f'Event {eid}: activity API does not expose persisted trace/result')
                    results = request(prefix + '/results/' + kind)
                    if not any(r['id'] == saved.id and r['provider_id'] == expected_id and r['evidence'] == saved.data['evidence'] for r in results):
                        raise RuntimeError(f'Event {eid}: persisted result missing from dashboard API')
                    entry.update(status=event.status, attempts=event.attempts, execution_id=execution.id,
                                 result_id=saved.id, provider_id=saved.provider_id, duration_ms=execution.duration_ms,
                                 nodes=audit.details['nodes'])
                if db.scalar(select(EngineeringEvent).where(EngineeringEvent.source == 'github', EngineeringEvent.delivery_id == delivery)).id != a['event_id']:
                    raise RuntimeError('Persisted delivery identity mismatch')
            passed('Observed LangGraph paths, PostgreSQL results/statuses, audits and dashboard API results verified')
        report['status'] = 'passed'
    except Exception:
        report['status'] = 'failed'
        raise
    finally:
        Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
        print('Report saved:', report_path, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--pr-number', type=int)
    parser.add_argument('--sprint-id', type=int)
    parser.add_argument('--report', default='/tmp/sprintgraph-live-workflow-report.json')
    parser.add_argument('--session-only', action='store_true', help='For trusted browser runner; returns a short-lived token to its captured pipe')
    args = parser.parse_args()
    if args.project_id < 1:
        parser.error('Project ID must be positive')
    if not args.session_only and (not args.pr_number or not args.sprint_id or min(args.pr_number, args.sprint_id) < 1):
        parser.error('Positive --pr-number and --sprint-id are required')
    try:
        if args.session_only:
            print(verification_session(args.project_id))
        else:
            verify(args.project_id, args.pr_number, args.sprint_id, args.report)
    except RuntimeError as exc:
        parser.exit(1, f'Live workflow verification failed: {exc}\n')
    except (OSError, httpx.HTTPError):
        parser.exit(1, 'Live workflow verification could not reach local services or save its report.\n')


if __name__ == '__main__':
    main()
