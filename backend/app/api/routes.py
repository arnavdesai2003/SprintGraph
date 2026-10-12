import json
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import session
from app.models import (User, Project, EngineeringEvent, WorkflowExecution, PullRequestAnalysis, SprintSummary,
                        DetectedBlocker, TaskPriorityRecommendation, AuditLog)
from app.security.webhooks import github_signature_valid, shared_secret_valid
from app.security.auth import current_user, admin, passwords, token, project_for
from app.services.events import ingest
from app.services.metrics import summarize_events
router = APIRouter()

class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=200)

class RunRequest(BaseModel):
    workflow: Literal['pull_request', 'sprint_summary', 'blockers', 'priorities']
    number: int = Field(default=42, ge=1, strict=True)

class RepositoryIdentity(BaseModel):
    full_name: str = Field(min_length=3, max_length=250)

class GitHubPayload(BaseModel):
    action: str
    number: int = Field(ge=1, strict=True)
    repository: RepositoryIdentity

class JiraIssueIdentity(BaseModel):
    key: str = Field(pattern=r'^[A-Z][A-Z0-9_]*-[0-9]+$', max_length=100)

class JiraPayload(BaseModel):
    issue: JiraIssueIdentity

class RoleChange(BaseModel):
    role: Literal['admin', 'developer']
    confirmed: Literal[True]

@router.post('/auth/login')
def login(body: Login, db: Session = Depends(session)):
    user = db.scalar(select(User).where(User.email == body.email))
    # Hash verification also runs for unknown users to reduce account enumeration.
    encoded = user.password_hash if user else passwords.hash('non-user-dummy-password')
    if not passwords.verify(body.password, encoded) or not user:
        raise HTTPException(401, 'Invalid credentials')
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id,
                   action='auth.login', details={}))
    db.commit()
    return {'access_token': token(user), 'token_type': 'bearer'}

@router.get('/auth/me')
def me(user: User = Depends(current_user)):
    return {'id': user.id, 'email': user.email, 'role': user.role, 'organization_id': user.organization_id}

@router.get('/projects')
def projects(user: User = Depends(current_user), db: Session = Depends(session)):
    return [{'id': p.id, 'name': p.name, 'github_repository': p.github_repository, 'jira_key': p.jira_key} for p in db.scalars(select(Project).where(Project.organization_id == user.organization_id))]

@router.post('/projects/{project_id}/run', status_code=202)
def run(project_id: int, body: RunRequest, user: User = Depends(current_user), db: Session = Depends(session)):
    project = project_for(db, user, project_id)
    event, _ = ingest(db, project, 'manual', str(uuid.uuid4()), body.workflow, {'number': body.number}, user.id)
    return {'event_id': event.id, 'status': event.status}

@router.get('/projects/{project_id}/overview')
def overview(project_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
    project_for(db, user, project_id)
    events = db.scalars(select(EngineeringEvent).where(EngineeringEvent.project_id == project_id)).all()
    metrics = summarize_events([{'status': e.status, 'handling': e.handling, 'attempts': e.attempts,
        'event_type': e.event_type, 'created_at': e.created_at, 'completed_at': e.completed_at} for e in events])
    statuses = {status: sum(e.status == status for e in events) for status in sorted({e.status for e in events})}
    return {'total_events': metrics['events'], 'statuses': statuses,
            'p50_latency_ms': metrics['p50_end_to_end_ms'], 'p95_latency_ms': metrics['p95_end_to_end_ms'],
            'automated_events': metrics['automated'], 'measurement_mode': settings().mode,
            'llm_provider': settings().llm_provider, 'metrics': metrics}

@router.get('/projects/{project_id}/activity')
def activity(project_id: int, user: User = Depends(current_user), db: Session = Depends(session)):
    project = project_for(db, user, project_id)
    events = db.scalars(select(EngineeringEvent).where(EngineeringEvent.project_id == project_id).order_by(EngineeringEvent.id.desc()).limit(200)).all()
    traces = {a.details['execution_id']: a.details for a in db.scalars(select(AuditLog).where(
        AuditLog.organization_id == project.organization_id,
        AuditLog.action.in_(['workflow.succeeded', 'workflow.failed']),
        AuditLog.details['event_id'].as_integer().in_([event.id for event in events]))) if 'execution_id' in a.details}
    return [{'id': e.id, 'workflow': e.event_type, 'source': e.source, 'status': e.status, 'attempts': e.attempts,
             'created_at': e.created_at, 'completed_at': e.completed_at, 'error': e.error,
             'executions': [{'id': x.id, 'status': x.status, 'duration_ms': x.duration_ms, 'error': x.error, 'result': x.result, 'trace': traces.get(x.id)} for x in db.scalars(select(WorkflowExecution).where(WorkflowExecution.event_id == e.id))]} for e in events]

@router.get('/projects/{project_id}/results/{kind}')
def results(project_id: int, kind: Literal['pull_request', 'sprint_summary', 'blockers', 'priorities'], user: User = Depends(current_user), db: Session = Depends(session)):
    project_for(db, user, project_id)
    model = {'pull_request': PullRequestAnalysis, 'sprint_summary': SprintSummary, 'blockers': DetectedBlocker, 'priorities': TaskPriorityRecommendation}[kind]
    return [{'id': r.id, 'created_at': r.created_at, **r.data} for r in db.scalars(select(model).where(model.project_id == project_id).order_by(model.id.desc()).limit(100))]

@router.get('/settings')
def configuration(user: User = Depends(admin), db: Session = Depends(session)):
    c = settings()
    return {'mode': c.mode, 'llm_provider': c.llm_provider, 'llm_model': c.llm_model,
            'llm_inference_enabled': c.llm_inference_enabled,
            'llm_ready': bool(c.llm_api_key and c.llm_model and c.llm_base_url),
            'github_configured': bool(c.github_token), 'jira_configured': bool(c.jira_url and c.jira_token and c.jira_email),
            'external_actions': 'Read-only integrations; no external mutation tools are enabled',
            'users': [{'id': u.id, 'email': u.email, 'role': u.role} for u in db.scalars(select(User).where(User.organization_id == user.organization_id))]}

@router.patch('/users/{user_id}/role')
def role(user_id: int, body: RoleChange, user: User = Depends(admin), db: Session = Depends(session)):
    target = db.get(User, user_id)
    if not target or target.organization_id != user.organization_id:
        raise HTTPException(404, 'User not found')
    if target.id == user.id:
        raise HTTPException(409, 'Cannot change your own role')
    target.role = body.role
    db.add(AuditLog(organization_id=user.organization_id, actor_id=user.id, action='user.role_changed', details={'user_id': target.id, 'role': body.role}))
    db.commit()
    return {'id': target.id, 'role': target.role}

@router.get('/audit')
def audit(user: User = Depends(admin), db: Session = Depends(session)):
    return [{'id': a.id, 'action': a.action, 'actor_id': a.actor_id, 'details': a.details, 'created_at': a.created_at} for a in db.scalars(select(AuditLog).where(AuditLog.organization_id == user.organization_id).order_by(AuditLog.id.desc()).limit(200))]

async def verified_body(request: Request, secret: str, signature: str, hmac_mode=True):
    if not secret:
        raise HTTPException(503, 'Webhook verification is not configured')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1_000_000:
            raise HTTPException(413, 'Payload too large')
    valid = github_signature_valid(bytes(raw), secret, signature) if hmac_mode else shared_secret_valid(secret, signature)
    if not valid:
        raise HTTPException(401, 'Invalid webhook authentication')
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError()
        return body
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'Invalid JSON object') from None

@router.post('/webhooks/github', status_code=202)
async def github(request: Request, db: Session = Depends(session)):
    body = await verified_body(request, settings().github_webhook_secret, request.headers.get('x-hub-signature-256', ''))
    delivery = request.headers.get('x-github-delivery', '')
    if not delivery or len(delivery) > 200:
        raise HTTPException(400, 'Delivery ID required')
    if request.headers.get('x-github-event') != 'pull_request' or body.get('action') not in {'opened', 'synchronize', 'edited', 'reopened'}:
        return {'status': 'ignored'}
    try:
        validated = GitHubPayload.model_validate(body)
    except ValueError:
        raise HTTPException(422, 'Invalid pull request payload') from None
    repository = validated.repository.full_name
    project = db.scalar(select(Project).where(Project.github_repository == repository))
    if not project:
        raise HTTPException(404, 'Repository not configured')
    number = validated.number
    event, created = ingest(db, project, 'github', delivery, 'pull_request', {'number': number})
    return {'event_id': event.id, 'duplicate': not created}

@router.post('/webhooks/jira/{project_id}', status_code=202)
async def jira(project_id: int, request: Request, db: Session = Depends(session)):
    # Supported configuration: an automation rule sends a shared-secret Authorization header.
    body = await verified_body(request, settings().jira_webhook_secret, request.headers.get('authorization', '').removeprefix('Bearer '), False)
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, 'Project not configured')
    try:
        key = JiraPayload.model_validate(body).issue.key
    except ValueError:
        raise HTTPException(422, 'Invalid Jira issue payload') from None
    if not isinstance(key, str) or not key.startswith(project.jira_key + '-'):
        raise HTTPException(422, 'Issue does not belong to project')
    delivery = request.headers.get('x-delivery-id', '')
    if not delivery or len(delivery) > 200:
        raise HTTPException(400, 'X-Delivery-ID required')
    event, created = ingest(db, project, 'jira', delivery, 'blockers', {'issue_key': key})
    return {'event_id': event.id, 'duplicate': not created}
