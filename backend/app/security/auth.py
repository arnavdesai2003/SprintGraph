from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import session
from app.models import User, Project
passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
def token(user: User):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)},
                      settings().jwt_secret, algorithm='HS256')
def current_user(auth: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(session)):
    try:
        claims = jwt.decode(auth.credentials if auth else '', settings().jwt_secret, algorithms=['HS256'],
                            options={'require': ['sub', 'exp']})
        subject = claims['sub']
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal() or int(subject) < 1:
            raise ValueError()
        user = db.get(User, int(subject))
        if not user or user.role not in {'admin', 'developer'}:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError, TypeError, OverflowError):
        raise HTTPException(401, 'Authentication required') from None

def admin(user: User = Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Admin role required')
    return user

def project_for(db, user, project_id):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.organization_id == user.organization_id))
    if not project:
        raise HTTPException(404, 'Project not found')
    return project
