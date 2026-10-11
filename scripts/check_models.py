"""Offline schema validation using real SQLAlchemy (no integration stubs)."""
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.services.events import ingest, retry_delay
from app.models import Base, Organization, Project, EngineeringEvent, WorkflowExecution, PullRequestAnalysis
engine = create_engine('sqlite://')
Base.metadata.create_all(engine)
assert len(Base.metadata.tables) == 11
with Session(engine) as db:
    org = Organization(name='Schema validation')
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name='Demo', github_repository='demo/repo', jira_key='DEMO')
    db.add(project)
    db.flush()
    event = EngineeringEvent(project_id=project.id, source='github', delivery_id='d1', event_type='pull_request', payload={'number': 1})
    db.add(event)
    db.flush()
    execution = WorkflowExecution(event_id=event.id, workflow='pull_request', status='succeeded', duration_ms=10)
    db.add(execution)
    db.flush()
    db.add(PullRequestAnalysis(project_id=project.id, execution_id=execution.id, provider_id='demo/repo#1', data={'summary': 'Persisted'}))
    db.commit()
    assert db.scalar(select(PullRequestAnalysis)).data['summary'] == 'Persisted'
    assert db.get(EngineeringEvent, event.id).status == 'pending'
    assert isinstance(db.get(EngineeringEvent, event.id).created_at, datetime)
    db.add(EngineeringEvent(project_id=project.id, source='github', delivery_id='d1', event_type='pull_request', payload={}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError('Delivery uniqueness not enforced')
    first, created = ingest(db, project, 'manual', 'database-check', 'priorities', {})
    second, new = ingest(db, project, 'manual', 'database-check', 'priorities', {})
    assert created and not new and first.id == second.id
    assert retry_delay(2).total_seconds() == 4
    assert retry_delay(30).total_seconds() == 300
print('PASS: 11 tables, relationships, defaults, JSON persistence, duplicate delivery constraint')
