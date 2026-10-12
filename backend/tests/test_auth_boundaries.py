"""Session validation and current database permissions across organization boundaries."""
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from sqlalchemy import select
from app.config import settings
from app.models import AuditLog, Organization, Project, User
from app.security.auth import passwords


def signed(claims):
    return {'Authorization': 'Bearer ' + jwt.encode(claims, settings().jwt_secret, algorithm='HS256')}


@pytest.mark.parametrize('claims', [
    {'sub': '1'},
    {'sub': '1', 'exp': 1},
    {'sub': None, 'exp': 9999999999},
    {'sub': '-1', 'exp': 9999999999},
    {'sub': '1.0', 'exp': 9999999999},
    {'sub': '999999', 'exp': 9999999999},
])
def test_invalid_session_returns_safe_401(client, claims):
    response = client.get('/api/auth/me', headers=signed(claims))
    assert response.status_code == 401
    assert response.json() == {'detail': 'Authentication required'}


def test_login_audit_contains_no_credentials(client, db):
    response = client.post('/api/auth/login', json={'email': 'admin@sprintgraph.local',
                           'password': 'test-demo-password-1234'})
    assert response.status_code == 200
    audit = db.scalar(select(AuditLog).where(AuditLog.action == 'auth.login'))
    assert audit.actor_id == 1 and audit.organization_id == 1 and audit.details == {}
    assert response.json()['access_token'] not in str(audit.details)


def test_existing_token_observes_role_revocation(client, headers, db):
    user = db.get(User, 1)
    user.role = 'developer'
    db.commit()
    assert client.get('/api/settings', headers=headers).status_code == 403
    assert client.get('/api/audit', headers=headers).status_code == 403
    assert client.get('/api/auth/me', headers=headers).json()['role'] == 'developer'
    user.role = 'invalid-role'
    db.commit()
    assert client.get('/api/auth/me', headers=headers).status_code == 401


def test_cross_organization_reads_runs_and_role_changes_are_hidden(client, headers, db):
    org = Organization(name='Isolated organization')
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name='Isolated project',
                      github_repository='isolated/repository', jira_key='OTHER', jira_board_id=7)
    user = User(organization_id=org.id, email='isolated@example.invalid', role='developer',
                password_hash=passwords.hash('test-isolation-password'))
    db.add_all([project, user])
    db.commit()
    for suffix in ['overview', 'activity', 'results/pull_request', 'results/sprint_summary',
                   'results/blockers', 'results/priorities']:
        assert client.get(f'/api/projects/{project.id}/{suffix}', headers=headers).status_code == 404
    assert client.post(f'/api/projects/{project.id}/run', headers=headers,
                       json={'workflow': 'pull_request', 'number': 2}).status_code == 404
    assert client.patch(f'/api/users/{user.id}/role', headers=headers,
                        json={'role': 'admin', 'confirmed': True}).status_code == 404
    assert all(p['id'] != project.id for p in client.get('/api/projects', headers=headers).json())
    assert all(u['id'] != user.id for u in client.get('/api/settings', headers=headers).json()['users'])


def test_deleted_account_cannot_use_existing_token(client, headers, db):
    user = User(organization_id=1, email='deleted@example.invalid', role='developer',
                password_hash=passwords.hash('test-deletion-password'))
    db.add(user)
    db.commit()
    credential = signed({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)})
    db.delete(user)
    db.commit()
    assert client.get('/api/auth/me', headers=credential).status_code == 401
