"""add_employee_fields_category_icon_and_mahalla_stats

Revision ID: e12d3bf5139c
Revises: e7da11e2c414
Create Date: 2026-09-15 12:48:15.659949

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e12d3bf5139c'
down_revision: Union[str, Sequence[str], None] = 'e7da11e2c414'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New columns on categories and users
    op.add_column('categories', sa.Column('icon_url', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('photo_url', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('birth_date_text', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('appointed_date_text', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('specialization', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('previous_workplace', sa.String(length=255), nullable=True))

    # 2. Mahalla Stats table
    op.create_table(
        'mahalla_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('mahalla_id', sa.BigInteger(), nullable=False),
        sa.Column('maydoni', sa.String(length=100), nullable=True),
        sa.Column('xonadonlar_soni', sa.Integer(), nullable=True),
        sa.Column('savdo_dokonlari_soni', sa.Integer(), nullable=True),
        sa.Column('maktablar_soni', sa.Integer(), nullable=True),
        sa.Column('kochalar_soni', sa.Integer(), nullable=True),
        sa.Column('mtm_soni', sa.Integer(), nullable=True),
        sa.Column('aholi_soni', sa.Integer(), nullable=True),
        sa.Column('erkaklar_soni', sa.Integer(), nullable=True),
        sa.Column('ayollar_soni', sa.Integer(), nullable=True),
        sa.Column('yoshlar_soni', sa.Integer(), nullable=True),
        sa.Column('voyaga_etmaganlar_soni', sa.Integer(), nullable=True),
        sa.Column('oilalar_soni', sa.Integer(), nullable=True),
        sa.Column('ijarada_yashovchilar_soni', sa.Integer(), nullable=True),
        sa.Column('chetga_ketganlar_soni', sa.Integer(), nullable=True),
        sa.Column('chetga_ketganlar_erkak', sa.Integer(), nullable=True),
        sa.Column('chetga_ketganlar_ayol', sa.Integer(), nullable=True),
        sa.Column('chetga_ketganlar_voyaga_etmagan', sa.Integer(), nullable=True),
        sa.Column('toifa', sa.String(length=255), nullable=True),
        sa.Column('aholi_oqimi', sa.String(length=255), nullable=True),
        sa.Column('murojaatlar_soni', sa.String(length=255), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['mahalla_id'], ['mahallas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index(op.f('ix_mahalla_stats_mahalla_id'), 'mahalla_stats', ['mahalla_id'], unique=True, if_not_exists=True)


def downgrade() -> None:
    op.drop_table('mahalla_stats')
    op.drop_column('users', 'previous_workplace')
    op.drop_column('users', 'specialization')
    op.drop_column('users', 'appointed_date_text')
    op.drop_column('users', 'birth_date_text')
    op.drop_column('users', 'photo_url')
    op.drop_column('categories', 'icon_url')
