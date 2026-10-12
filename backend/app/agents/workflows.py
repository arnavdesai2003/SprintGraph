import re
from datetime import date, datetime, timezone
from langgraph.graph import END, START, StateGraph
from app.agents.schemas import (State, RoutingInput, ProjectContext, PRPayload, SprintPayload,
                                PREvidence, SprintEvidence, PRResult, SprintResult, BlockerResult, PriorityResult)
from app.agents.tracing import tracked
from app.config import settings
from app.agents.inference import describe
from app.services.scoring import DONE, prioritize, detect_blockers
from app.integrations.clients import Clients

def classify(state: State):
    route = RoutingInput.model_validate(state)
    project = ProjectContext.model_validate(state['project'], from_attributes=True)
    model = PRPayload if route.event_type == 'pull_request' else SprintPayload
    payload = model.model_validate(route.payload).model_dump(exclude_none=True)
    if payload.get('issue_key') and not payload['issue_key'].startswith(project.jira_key + '-'):
        raise ValueError('Issue does not belong to the configured project')
    return {'event_type': route.event_type, 'payload': payload, 'project': project,
            'reference_date': datetime.now(timezone.utc).date().isoformat()}

async def collect(state: State):
    client = Clients()
    project = state['project']
    if state['event_type'] == 'pull_request':
        evidence = await client.pull_request(project.github_repository, state['payload']['number'])
        evidence['linked_issues'] = sorted(set(re.findall(r'\b[A-Z][A-Z0-9_]*-\d+\b', evidence['title'] + ' ' + evidence['body'])))
        evidence = PREvidence.model_validate(evidence).model_dump(mode='json')
        if evidence['repository'] != project.github_repository or evidence['number'] != state['payload']['number']:
            raise ValueError('Provider PR identity does not match the requested resource')
        if evidence['url'] != f'https://github.com/{project.github_repository}/pull/{evidence["number"]}':
            raise ValueError('Provider PR URL does not match the requested resource')
    else:
        evidence = await client.sprint(project)
        evidence = SprintEvidence.model_validate({**evidence, 'reference_date': state['reference_date']}).model_dump(mode='json')
        if any(not issue['key'].startswith(project.jira_key + '-') for issue in evidence['issues']):
            raise ValueError('Provider issue does not belong to the configured project')
    return {'evidence': evidence}

async def analyze_pr(state: State):
    evidence = state['evidence']
    analysis = await describe(evidence, {'summary': f'PR #{evidence["number"]}: {evidence["title"]}. Changes {len(evidence["files"])} files.',
        'risks': ['Review signature validation and retry boundaries.'], 'testing': ['Verify duplicate deliveries and provider failures.'],
        'recommendations': ['Review manually before approval; this analysis is advisory.']})
    return {'output': {'provider_id': f'{evidence["repository"]}#{evidence["number"]}', 'analysis': analysis, 'evidence': evidence}}

async def summarize(state: State):
    evidence = state['evidence']
    counts = {}
    for issue in evidence['issues']:
        counts[issue['status']] = counts.get(issue['status'], 0) + 1
    completed = sum(v for k, v in counts.items() if k.lower() in DONE)
    analysis = await describe(evidence, {'summary': f'{evidence["name"]}: {completed} of {len(evidence["issues"])} issues completed. Review blocked and aging work.'})
    return {'output': {'provider_id': evidence['id'], 'analysis': analysis, 'distribution': counts,
                       'progress': completed / max(1, len(evidence['issues'])), 'evidence': evidence}}

async def blockers(state: State):
    evidence = state['evidence']
    items = detect_blockers(evidence['issues'], today=date.fromisoformat(evidence['reference_date']),
                            stalled_days=settings().stalled_days)
    analysis = await describe({'findings': items, 'issues': evidence['issues']},
                              {'summary': f'{len(items)} blocker signals found. Definite findings have explicit status, dependency or due-date evidence; stalled work is potential.'})
    # Correlate prior PR analyses during persistence; do not invent external PR links.
    return {'output': {'provider_id': evidence['id'], 'items': items, 'analysis': analysis, 'evidence': evidence}}

async def priorities(state: State):
    evidence = state['evidence']
    items = prioritize(evidence['issues'], today=date.fromisoformat(evidence['reference_date']),
                       weights=settings().priority_weights)
    analysis = await describe({'ranking': items}, {'summary': 'Ranking uses explicit priority, severity, due date, dependencies, sprint commitment, and status weights.'})
    return {'output': {'provider_id': evidence['id'], 'items': items, 'analysis': analysis, 'evidence': evidence}}

def validate(state: State):
    kind = state['event_type']
    models = {'pull_request': PRResult, 'sprint_summary': SprintResult,
              'blockers': BlockerResult, 'priorities': PriorityResult}
    output = models[kind].model_validate(state['output']).model_dump(mode='json')
    evidence = output['evidence']
    if evidence != state['evidence']:
        raise ValueError('Workflow changed validated source evidence')
    expected_id = f'{evidence["repository"]}#{evidence["number"]}' if kind == 'pull_request' else evidence['id']
    if output['provider_id'] != expected_id:
        raise ValueError('Result provider identity does not match evidence')
    if kind == 'sprint_summary':
        counts = {}
        for issue in evidence['issues']:
            counts[issue['status']] = counts.get(issue['status'], 0) + 1
        completed = sum(value for key, value in counts.items() if key.lower() in DONE)
        if output['distribution'] != counts or output['progress'] != completed / max(1, len(evidence['issues'])):
            raise ValueError('Sprint metrics do not match source evidence')
    if kind == 'priorities':
        expected = prioritize(evidence['issues'], today=date.fromisoformat(evidence['reference_date']),
                              weights=settings().priority_weights)
        if output['items'] != expected:
            raise ValueError('Priority ranking differs from deterministic business rules')
    if kind == 'blockers':
        expected = detect_blockers(evidence['issues'], today=date.fromisoformat(evidence['reference_date']),
                                   stalled_days=settings().stalled_days)
        findings = [{key: value for key, value in item.items() if key != 'pull_requests'} for item in output['items']]
        if findings != expected:
            raise ValueError('Blocker findings differ from source evidence')
    return {'output': output}

def build_graph():
    graph = StateGraph(State)
    graph.add_node('collect', tracked('collect', collect))
    graph.add_node('classify', tracked('classify', classify))
    graph.add_edge(START, 'classify')
    graph.add_edge('classify', 'collect')
    for name, node in [('pull_request', analyze_pr), ('sprint_summary', summarize), ('blockers', blockers), ('priorities', priorities)]:
        graph.add_node(name, tracked(name, node))
        graph.add_edge(name, 'validate')
    graph.add_conditional_edges('collect', lambda state: state['event_type'], {name: name for name in ['pull_request', 'sprint_summary', 'blockers', 'priorities']})
    graph.add_node('validate', tracked('validate', validate))
    graph.add_edge('validate', END)
    return graph.compile()

graph = build_graph()
