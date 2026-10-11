from datetime import date

PRIORITY_WEIGHTS = {'Highest': 50, 'High': 35, 'Medium': 20, 'Low': 10, 'Lowest': 0}
DONE = {'done', 'closed', 'resolved'}

def prioritize(issues, today=None, weights=None):
    today = today or date.today()
    weights = weights or PRIORITY_WEIGHTS
    blocked_by = {}
    for issue in issues:
        if issue['status'].lower() not in DONE:
            for key in issue['dependencies']:
                blocked_by[key] = blocked_by.get(key, 0) + 1
    results = []
    for issue in issues:
        if issue['status'].lower() in DONE:
            continue
        parts = {'priority': weights.get(issue['priority'], 20), 'severity': issue.get('severity', 0) * 5,
                 'sprint': 10 if issue['sprint'] else 0, 'unblocks': 15 * blocked_by.get(issue['key'], 0),
                 'in_progress': 5 if issue['status'].lower() == 'in progress' else 0, 'due': 0}
        if issue.get('due_date'):
            days = (date.fromisoformat(issue['due_date']) - today).days
            parts['due'] = 25 if days < 0 else 15 if days <= 3 else 5 if days <= 7 else 0
        results.append({**issue, 'score': sum(parts.values()), 'components': parts,
                        'explanation': ', '.join(f'{key}: +{value}' for key, value in parts.items() if value) or 'No positive scoring contributions.'})
    return sorted(results, key=lambda i: (-i['score'], i['key']))

def detect_blockers(issues, today=None, stalled_days=7):
    today = today or date.today()
    by_key = {i['key']: i for i in issues}
    findings = []
    for issue in issues:
        if issue['status'].lower() in DONE:
            continue
        def add(kind, certainty, evidence, recommendation):
            findings.append({'issue_key': issue['key'], 'kind': kind, 'certainty': certainty,
                             'evidence': evidence, 'recommendation': recommendation})
        if issue['status'].lower() == 'blocked':
            add('explicit', 'definite', 'Jira status is Blocked', 'Assign an owner to resolve the blocker')
        for dependency in issue['dependencies']:
            if dependency not in by_key or by_key[dependency]['status'].lower() not in DONE:
                add('dependency', 'definite' if dependency in by_key else 'potential', f'Unresolved dependency {dependency}', f'Check dependency {dependency}')
        if (today - date.fromisoformat(issue['updated'][:10])).days >= stalled_days:
            add('stalled', 'potential', f'Last update: {issue["updated"]}', 'Confirm progress with the issue owner')
        if issue.get('due_date') and date.fromisoformat(issue['due_date']) < today:
            add('overdue', 'definite', f'Due date: {issue["due_date"]}', 'Reassess scope and due date')
    return findings

