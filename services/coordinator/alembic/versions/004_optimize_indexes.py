"""optimize indexes for jobs, workers, and events

Revision ID: 004_optimize_indexes
Revises: 003_add_supported_models
Create Date: 2026-10-12 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '004_optimize_indexes'
down_revision: Union[str, None] = '003_add_supported_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Index on jobs.assigned_worker_id
    op.create_index('ix_jobs_assigned_worker_id', 'jobs', ['assigned_worker_id'], unique=False)
    # 2. Composite index on jobs (assigned_worker_id, status)
    op.create_index('ix_jobs_assigned_worker_status', 'jobs', ['assigned_worker_id', 'status'], unique=False)
    # 3. Composite index on jobs (status, created_at)
    op.create_index('ix_jobs_status_created_at', 'jobs', ['status', 'created_at'], unique=False)
    # 4. Composite index on workers (connection_status, last_heartbeat)
    op.create_index('ix_workers_status_last_heartbeat', 'workers', ['connection_status', 'last_heartbeat'], unique=False)
    # 5. Index on job_events.created_at
    op.create_index('ix_job_events_created_at', 'job_events', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_job_events_created_at', table_name='job_events')
    op.drop_index('ix_workers_status_last_heartbeat', table_name='workers')
    op.drop_index('ix_jobs_status_created_at', table_name='jobs')
    op.drop_index('ix_jobs_assigned_worker_status', table_name='jobs')
    op.drop_index('ix_jobs_assigned_worker_id', table_name='jobs')
