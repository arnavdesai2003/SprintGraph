from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default='developer')

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    name: Mapped[str] = mapped_column(String(200))
    github_repository: Mapped[str] = mapped_column(String(250), unique=True)
    jira_key: Mapped[str] = mapped_column(String(50))
    jira_board_id: Mapped[int] = mapped_column(default=1)

class IntegrationConfiguration(Base):
    __tablename__ = 'integration_configurations'
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    configuration: Mapped[dict] = mapped_column(JSON, default=dict)

class EngineeringEvent(Base):
    __tablename__ = 'engineering_events'
    __table_args__ = (UniqueConstraint('source', 'delivery_id', name='uq_event_delivery'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    source: Mapped[str] = mapped_column(String(30))
    delivery_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    handling: Mapped[str] = mapped_column(String(20), default='automated')

class WorkflowExecution(Base):
    __tablename__ = 'workflow_executions'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('engineering_events.id'))
    workflow: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    duration_ms: Mapped[float | None]
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ResultMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey('workflow_executions.id'), unique=True)
    provider_id: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class PullRequestAnalysis(ResultMixin, Base):
    __tablename__ = 'pull_request_analyses'
class SprintSummary(ResultMixin, Base):
    __tablename__ = 'sprint_summaries'
class DetectedBlocker(ResultMixin, Base):
    __tablename__ = 'detected_blockers'
class TaskPriorityRecommendation(ResultMixin, Base):
    __tablename__ = 'task_priority_recommendations'

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id'))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
