"""add_seen_fields_to_documents

Revision ID: a12b3c4d5e6f
Revises: f91a2b3c4d5e
Create Date: 2026-09-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a12b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = 'f91a2b3c4d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('check_in_documents', sa.Column('seen_at', sa.DateTime(), nullable=True))
    op.add_column('check_in_documents', sa.Column('seen_by_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('check_in_documents', 'seen_by_id')
    op.drop_column('check_in_documents', 'seen_at')

