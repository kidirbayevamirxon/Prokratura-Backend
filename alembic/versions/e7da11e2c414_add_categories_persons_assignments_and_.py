"""add_categories_persons_assignments_and_documents

Revision ID: e7da11e2c414
Revises: 0b76332b6877
Create Date: 2026-09-15 12:10:49.866239

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7da11e2c414'
down_revision: Union[str, Sequence[str], None] = '0b76332b6877'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('assigned_roles', sa.JSON(), nullable=False),
        sa.Column('default_frequency_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('is_active', sa.Boolean(), server_default='t', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True, if_not_exists=True)

    # 2. Persons table
    op.create_table(
        'persons',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=False),
        sa.Column('mahalla_id', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='t', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['mahalla_id'], ['mahallas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index(op.f('ix_persons_full_name'), 'persons', ['full_name'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_persons_mahalla_id'), 'persons', ['mahalla_id'], unique=False, if_not_exists=True)

    # 3. Person Category Assignments table
    op.create_table(
        'person_category_assignments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('person_id', sa.BigInteger(), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=False),
        sa.Column('mahalla_id', sa.BigInteger(), nullable=False),
        sa.Column('frequency_days', sa.Integer(), nullable=False),
        sa.Column('assigned_roles', sa.JSON(), nullable=True),
        sa.Column('next_check_in_due', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
        sa.Column('created_by_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['mahalla_id'], ['mahallas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index(op.f('ix_person_category_assignments_category_id'), 'person_category_assignments', ['category_id'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_person_category_assignments_mahalla_id'), 'person_category_assignments', ['mahalla_id'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_person_category_assignments_next_check_in_due'), 'person_category_assignments', ['next_check_in_due'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_person_category_assignments_person_id'), 'person_category_assignments', ['person_id'], unique=False, if_not_exists=True)

    # 4. Check In Documents table
    op.create_table(
        'check_in_documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('assignment_id', sa.BigInteger(), nullable=False),
        sa.Column('person_id', sa.BigInteger(), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=False),
        sa.Column('mahalla_id', sa.BigInteger(), nullable=False),
        sa.Column('submitted_by_id', sa.BigInteger(), nullable=False),
        sa.Column('doc_type', sa.String(length=50), server_default='regular', nullable=False),
        sa.Column('photo_url', sa.String(length=500), nullable=False),
        sa.Column('pdf_url', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('check_in_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('reviewed_by_id', sa.BigInteger(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['person_category_assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mahalla_id'], ['mahallas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submitted_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index(op.f('ix_check_in_documents_assignment_id'), 'check_in_documents', ['assignment_id'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_check_in_documents_category_id'), 'check_in_documents', ['category_id'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_check_in_documents_mahalla_id'), 'check_in_documents', ['mahalla_id'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_check_in_documents_person_id'), 'check_in_documents', ['person_id'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_check_in_documents_submitted_by_id'), 'check_in_documents', ['submitted_by_id'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_table('check_in_documents')
    op.drop_table('person_category_assignments')
    op.drop_table('persons')
    op.drop_table('categories')
