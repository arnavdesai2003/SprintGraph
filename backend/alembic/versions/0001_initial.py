"""Frozen initial SprintGraph schema."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('organizations',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False, primary_key=False),
    )
    op.create_table('projects',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False, primary_key=False),
        sa.Column('name', sa.String(length=200), nullable=False, primary_key=False),
        sa.Column('github_repository', sa.String(length=250), nullable=False, primary_key=False),
        sa.Column('jira_key', sa.String(length=50), nullable=False, primary_key=False),
        sa.Column('jira_board_id', sa.Integer(), nullable=False, primary_key=False),
        sa.UniqueConstraint('github_repository', name=None),
    )
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False, primary_key=False),
        sa.Column('email', sa.String(length=254), nullable=False, primary_key=False),
        sa.Column('password_hash', sa.Text(), nullable=False, primary_key=False),
        sa.Column('role', sa.String(length=20), nullable=False, primary_key=False),
        sa.UniqueConstraint('email', name=None),
    )
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False, primary_key=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, primary_key=False),
        sa.Column('action', sa.String(length=100), nullable=False, primary_key=False),
        sa.Column('details', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_table('engineering_events',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False, primary_key=False),
        sa.Column('source', sa.String(length=30), nullable=False, primary_key=False),
        sa.Column('delivery_id', sa.String(length=200), nullable=False, primary_key=False),
        sa.Column('event_type', sa.String(length=40), nullable=False, primary_key=False),
        sa.Column('payload', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('status', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('attempts', sa.Integer(), nullable=False, primary_key=False),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, primary_key=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, primary_key=False),
        sa.Column('error', sa.Text(), nullable=True, primary_key=False),
        sa.Column('handling', sa.String(length=20), nullable=False, primary_key=False),
        sa.UniqueConstraint('source', 'delivery_id', name='uq_event_delivery'),
    )
    op.create_index('ix_engineering_events_project_id', 'engineering_events', ['project_id'], unique=False)
    op.create_index('ix_engineering_events_status', 'engineering_events', ['status'], unique=False)
    op.create_table('integration_configurations',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False, primary_key=False),
        sa.Column('provider', sa.String(length=30), nullable=False, primary_key=False),
        sa.Column('configuration', sa.JSON(), nullable=False, primary_key=False),
    )
    op.create_index('ix_integration_configurations_project_id', 'integration_configurations', ['project_id'], unique=False)
    op.create_table('workflow_executions',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('event_id', sa.Integer(), sa.ForeignKey('engineering_events.id'), nullable=False, primary_key=False),
        sa.Column('workflow', sa.String(length=40), nullable=False, primary_key=False),
        sa.Column('status', sa.String(length=20), nullable=False, primary_key=False),
        sa.Column('duration_ms', sa.Float(), nullable=True, primary_key=False),
        sa.Column('result', sa.JSON(), nullable=True, primary_key=False),
        sa.Column('error', sa.Text(), nullable=True, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
    )
    op.create_table('detected_blockers',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False, primary_key=False),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('workflow_executions.id'), nullable=False, primary_key=False),
        sa.Column('provider_id', sa.String(length=200), nullable=False, primary_key=False),
        sa.Column('data', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('execution_id', name=None),
    )
    op.create_index('ix_detected_blockers_project_id', 'detected_blockers', ['project_id'], unique=False)
    op.create_table('pull_request_analyses',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False, primary_key=False),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('workflow_executions.id'), nullable=False, primary_key=False),
        sa.Column('provider_id', sa.String(length=200), nullable=False, primary_key=False),
        sa.Column('data', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('execution_id', name=None),
    )
    op.create_index('ix_pull_request_analyses_project_id', 'pull_request_analyses', ['project_id'], unique=False)
    op.create_table('sprint_summaries',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False, primary_key=False),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('workflow_executions.id'), nullable=False, primary_key=False),
        sa.Column('provider_id', sa.String(length=200), nullable=False, primary_key=False),
        sa.Column('data', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('execution_id', name=None),
    )
    op.create_index('ix_sprint_summaries_project_id', 'sprint_summaries', ['project_id'], unique=False)
    op.create_table('task_priority_recommendations',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False, primary_key=False),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('workflow_executions.id'), nullable=False, primary_key=False),
        sa.Column('provider_id', sa.String(length=200), nullable=False, primary_key=False),
        sa.Column('data', sa.JSON(), nullable=False, primary_key=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, primary_key=False),
        sa.UniqueConstraint('execution_id', name=None),
    )
    op.create_index('ix_task_priority_recommendations_project_id', 'task_priority_recommendations', ['project_id'], unique=False)

def downgrade():
    op.drop_table('task_priority_recommendations')
    op.drop_table('sprint_summaries')
    op.drop_table('pull_request_analyses')
    op.drop_table('detected_blockers')
    op.drop_table('workflow_executions')
    op.drop_table('integration_configurations')
    op.drop_table('engineering_events')
    op.drop_table('audit_logs')
    op.drop_table('users')
    op.drop_table('projects')
    op.drop_table('organizations')
