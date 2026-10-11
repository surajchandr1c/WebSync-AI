"""add max_concurrent_jobs to workers and placement_reason to jobs

Revision ID: 002_phase4_scheduler_schema
Revises: 001_initial_schema
Create Date: 2026-10-11 23:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_phase4_scheduler_schema'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workers', sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('jobs', sa.Column('placement_reason', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'placement_reason')
    op.drop_column('workers', 'max_concurrent_jobs')
