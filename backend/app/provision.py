"""Trusted local operator command to provision an organization, admin and project."""
import argparse
import getpass
import re
from sqlalchemy import select
from app.db import Session
from app.models import Organization, User, Project, IntegrationConfiguration, AuditLog
from app.security.auth import passwords

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--organization', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--repository', required=True, help='GitHub owner/repository')
    parser.add_argument('--jira-key', required=True)
    parser.add_argument('--board-id', type=int, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', args.repository) or args.repository.split('/')[-1] in {'.', '..'}:
        parser.error('Invalid repository')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,49}', args.jira_key) or args.board_id < 1:
        parser.error('Invalid Jira key or board ID')
    if '@' not in args.email or len(args.email) > 254 or not 1 <= len(args.organization) <= 200:
        parser.error('Invalid email or organization name')
    password = getpass.getpass('New administrator password (12+ characters): ')
    if len(password) < 12 or password != getpass.getpass('Confirm password: '):
        parser.error('Password too short or confirmation does not match')
    with Session() as db:
        if db.scalar(select(User).where(User.email == args.email)) or db.scalar(select(Project).where(Project.github_repository == args.repository)):
            parser.error('Email or repository is already provisioned; no changes made')
        organization = Organization(name=args.organization)
        db.add(organization)
        db.flush()
        user = User(organization_id=organization.id, email=args.email, password_hash=passwords.hash(password), role='admin')
        project = Project(organization_id=organization.id, name=args.organization, github_repository=args.repository,
                          jira_key=args.jira_key, jira_board_id=args.board_id)
        db.add_all([user, project])
        db.flush()
        for provider in ['github', 'jira']:
            db.add(IntegrationConfiguration(project_id=project.id, provider=provider, configuration={'credential_source': 'environment'}))
        db.add(AuditLog(organization_id=organization.id, actor_id=user.id, action='organization.provisioned', details={'project_id': project.id}))
        db.commit()
        print(f'Provisioned organization {organization.id}, project {project.id}; sign in with the supplied email.')

if __name__ == '__main__':
    main()
