"""add_due_date_to_documents

Revision ID: f91a2b3c4d5e
Revises: e12d3bf5139c
Create Date: 2026-09-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f91a2b3c4d5e'
down_revision: Union[str, Sequence[str], None] = 'e12d3bf5139c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('check_in_documents', sa.Column('due_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('check_in_documents', 'due_date')

