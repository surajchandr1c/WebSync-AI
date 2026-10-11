"""initial schema for users, workers, jobs, and job_events

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-11 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. workers
    op.create_table(
        'workers',
        sa.Column('worker_id', sa.String(length=128), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('hostname', sa.String(length=128), nullable=False),
        sa.Column('platform', sa.String(length=64), nullable=False),
        sa.Column('platform_version', sa.String(length=128), nullable=False),
        sa.Column('cpu_utilization', sa.Float(), nullable=False),
        sa.Column('total_ram_bytes', sa.BigInteger(), nullable=False),
        sa.Column('available_ram_bytes', sa.BigInteger(), nullable=False),
        sa.Column('supported_workloads', sa.JSON(), nullable=False),
        sa.Column('gpu_available', sa.Boolean(), nullable=False),
        sa.Column('gpu_metadata', sa.JSON(), nullable=False),
        sa.Column('active_job_count', sa.Integer(), nullable=False),
        sa.Column('connection_status', sa.String(length=32), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('auth_token_hash', sa.String(length=255), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('worker_id'),
    )
    op.create_index(op.f('ix_workers_worker_id'), 'workers', ['worker_id'], unique=False)
    op.create_index(op.f('ix_workers_connection_status'), 'workers', ['connection_status'], unique=False)

    # 3. jobs
    op.create_table(
        'jobs',
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('job_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('assigned_worker_id', sa.String(length=128), nullable=True),
        sa.Column('input_payload', sa.JSON(), nullable=False),
        sa.Column('requirements', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_exit_code', sa.Integer(), nullable=True),
        sa.Column('result_output', sa.Text(), nullable=True),
        sa.Column('result_duration_seconds', sa.Float(), nullable=True),
        sa.Column('result_error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_worker_id'], ['workers.worker_id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('job_id'),
    )
    op.create_index(op.f('ix_jobs_job_type'), 'jobs', ['job_type'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)

    # 4. job_events
    op.create_table(
        'job_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.job_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_job_events_job_id'), 'job_events', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_job_events_job_id'), table_name='job_events')
    op.drop_table('job_events')
    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_job_type'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_workers_connection_status'), table_name='workers')
    op.drop_index(op.f('ix_workers_worker_id'), table_name='workers')
    op.drop_table('workers')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
