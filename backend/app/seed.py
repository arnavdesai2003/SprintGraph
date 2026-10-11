import asyncio
from sqlalchemy import select
from app.config import settings
from app.db import Session
from app.models import Organization, User, Project, IntegrationConfiguration
from app.security.auth import passwords
from app.services.events import ingest
from app.worker import process_once

def seed():
    if settings().mode != 'demo' or len(settings().demo_password) < 12:
        raise ValueError('Seed requires demo mode and DEMO_PASSWORD of at least 12 characters')
    with Session() as db:
        project = db.scalar(select(Project).where(Project.github_repository == 'sprintgraph/demo'))
        if not project:
            org = Organization(name='SprintGraph Demo')
            db.add(org)
            db.flush()
            for email, role in [('admin@sprintgraph.local', 'admin'), ('developer@sprintgraph.local', 'developer')]:
                db.add(User(organization_id=org.id, email=email, role=role, password_hash=passwords.hash(settings().demo_password)))
            project = Project(organization_id=org.id, name='SprintGraph Platform', github_repository='sprintgraph/demo', jira_key='SG')
            db.add(project)
            db.flush()
            for provider in ['github', 'jira']:
                db.add(IntegrationConfiguration(project_id=project.id, provider=provider, configuration={'mode': 'demo'}))
            db.commit()
        for workflow in ['pull_request', 'sprint_summary', 'blockers', 'priorities']:
            ingest(db, project, 'demo', f'seed-{workflow}-v1', workflow, {'number': 42})

async def main():
    seed()
    while await process_once():
        pass

if __name__ == '__main__':
    asyncio.run(main())
