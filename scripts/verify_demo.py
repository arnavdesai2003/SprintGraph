"""Verify the running local demo using only Python's standard library.

Run from the repository root: python3 scripts/verify_demo.py
No credentials or bearer tokens are printed or included in the report.
"""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = 'http://localhost:8000/api'


def request(path, method='GET', body=None, token='', headers=None, expected=200):
    data = json.dumps(body).encode() if body is not None else None
    merged = {'Content-Type': 'application/json', **(headers or {})}
    if token:
        merged['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(API + path, data=data, headers=merged, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    if status != expected:
        # Response bodies can contain user data; keep the diagnostic bounded and generic.
        raise RuntimeError(f'{method} {path}: expected HTTP {expected}, received {status}')
    return json.loads(raw) if raw else None


def environment():
    values = {}
    for line in (ROOT / '.env').read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('\"\'')
    if values.get('MODE', 'demo') != 'demo':
        raise RuntimeError('This verification command only supports demo mode')
    if not values.get('DEMO_PASSWORD') or not values.get('GITHUB_WEBHOOK_SECRET'):
        raise RuntimeError('Configure DEMO_PASSWORD and GITHUB_WEBHOOK_SECRET in the private root .env')
    return values


def main():
    env = environment()
    checks = []

    def passed(label):
        checks.append(label)
        print('PASS:', label, flush=True)

    for url in ['http://localhost:8000/health', 'http://localhost:8000/ready', 'http://localhost:3000']:
        with urllib.request.urlopen(url, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f'Service check failed: {url}')
        passed(url)

    request('/projects', expected=401)
    passed('Anonymous API access rejected')
    admin = request('/auth/login', method='POST', body={
        'email': 'admin@sprintgraph.local', 'password': env['DEMO_PASSWORD']})['access_token']
    developer = request('/auth/login', method='POST', body={
        'email': 'developer@sprintgraph.local', 'password': env['DEMO_PASSWORD']})['access_token']
    request('/settings', token=developer, expected=403)
    request('/audit', token=developer, expected=403)
    request('/settings', token=admin)
    passed('Development login and Admin/Developer permissions')

    projects = request('/projects', token=admin)
    project = next((p for p in projects if p['github_repository'] == 'sprintgraph/demo'), None)
    if not project:
        raise RuntimeError('Demo project missing; inspect seed service logs')
    prefix = f'/projects/{project["id"]}'
    event_ids = {}
    for workflow in ['pull_request', 'sprint_summary', 'blockers', 'priorities']:
        result = request(prefix + '/run', method='POST', token=admin,
                         body={'workflow': workflow, 'number': 43}, expected=202)
        event_ids[result['event_id']] = workflow
    passed('All four workflows accepted into the persisted queue')

    payload = {'action': 'opened', 'number': 44, 'repository': {'full_name': 'sprintgraph/demo'}}
    raw = json.dumps(payload).encode()
    headers = {'X-GitHub-Event': 'pull_request', 'X-GitHub-Delivery': 'verify-' + str(uuid.uuid4()),
               'X-Hub-Signature-256': 'sha256=' + hmac.new(
                   env['GITHUB_WEBHOOK_SECRET'].encode(), raw, hashlib.sha256).hexdigest()}
    request('/webhooks/github', method='POST', body=payload,
            headers={**headers, 'X-Hub-Signature-256': 'sha256=invalid'}, expected=401)
    first = request('/webhooks/github', method='POST', body=payload, headers=headers, expected=202)
    second = request('/webhooks/github', method='POST', body=payload, headers=headers, expected=202)
    if first['duplicate'] or not second['duplicate'] or first['event_id'] != second['event_id']:
        raise RuntimeError('Webhook delivery deduplication failed')
    event_ids[first['event_id']] = 'pull_request'
    passed('Webhook signature rejection and delivery deduplication')

    deadline = time.monotonic() + 120
    last_status = None
    next_update = 0.0
    while True:
        activity = {e['id']: e for e in request(prefix + '/activity', token=admin)}
        snapshot = ', '.join(f'#{eid} {workflow}: {activity.get(eid, {}).get("status", "missing")} (attempts={activity.get(eid, {}).get("attempts", 0)})' for eid, workflow in event_ids.items())
        if snapshot != last_status or time.monotonic() >= next_update:
            print('WAIT:', snapshot, flush=True)
            last_status = snapshot
            next_update = time.monotonic() + 5
        failed = [eid for eid in event_ids if eid in activity and activity[eid]['status'] == 'failed']
        if failed:
            raise RuntimeError(f'Workflow events failed: {failed}; inspect worker logs')
        if all(eid in activity and activity[eid]['status'] == 'succeeded' for eid in event_ids):
            break
        if time.monotonic() >= deadline:
            pending = {eid: activity.get(eid, {}).get('status', 'missing') for eid in event_ids}
            raise RuntimeError(f'Timed out waiting for workflow completion: {pending}')
        time.sleep(1)

    for eid, workflow in event_ids.items():
        executions = activity[eid]['executions']
        result = next((e['result'] for e in executions if e.get('result')), None)
        if not result or not result.get('provider_id') or 'evidence' not in result:
            raise RuntimeError(f'Event #{eid} has no persisted structured result')
        results = request(prefix + '/results/' + workflow, token=admin)
        if not any(r['provider_id'] == result['provider_id'] for r in results):
            raise RuntimeError(f'Event #{eid} result is missing from the dashboard API')
    passed('Five events completed with persisted results available to dashboard APIs')
    audit = request('/audit', token=admin)
    if not any(a['action'] == 'workflow.succeeded' and a['details'].get('event_id') in event_ids for a in audit):
        raise RuntimeError('Successful workflow audit record missing')
    passed('Workflow completion is audited')
    report = {'mode': 'demo', 'checks': checks, 'event_ids': list(event_ids),
              'limitations': ['Does not replace pytest, frontend lint/typecheck, or browser interaction testing']}
    (ROOT / 'verification-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Verification passed. Report saved to verification-report.json.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit('Interrupted: verification is incomplete. Queued workflows remain in the database; inspect worker logs before retrying.') from None
    except (OSError, ValueError, RuntimeError) as exc:
        raise SystemExit(f'FAIL: {exc}') from None
