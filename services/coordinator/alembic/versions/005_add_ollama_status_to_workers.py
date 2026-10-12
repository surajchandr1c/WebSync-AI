"""add ollama_status and last_model_check to workers

Revision ID: 005_add_ollama_status
Revises: 004_optimize_indexes
Create Date: 2026-10-12 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '005_add_ollama_status'
down_revision: Union[str, None] = '004_optimize_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workers', sa.Column('ollama_status', sa.String(length=32), nullable=False, server_default='not_installed'))
    op.add_column('workers', sa.Column('last_model_check', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('workers', 'last_model_check')
    op.drop_column('workers', 'ollama_status')
