"""add supported_models to workers

Revision ID: 003_add_supported_models
Revises: 002_phase4_scheduler_schema
Create Date: 2026-10-12 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003_add_supported_models'
down_revision: Union[str, None] = '002_phase4_scheduler_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workers', sa.Column('supported_models', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('workers', 'supported_models')
