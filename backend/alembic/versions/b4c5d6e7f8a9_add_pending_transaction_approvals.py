"""Add pending_transaction_approvals + votes tables (multi-level approval by threshold)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pending_transaction_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mapping_id', sa.Integer(), nullable=True),
        sa.Column('mt_type', sa.String(), nullable=False),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('amount', sa.String(), nullable=True),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('output_filename', sa.String(), nullable=False),
        sa.Column('required_approvals', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('submitted_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['mapping_id'], ['mappings.id']),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pending_transaction_approvals_id'), 'pending_transaction_approvals', ['id'])

    op.create_table(
        'pending_transaction_approval_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('approver_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['transaction_id'], ['pending_transaction_approvals.id']),
        sa.ForeignKeyConstraint(['approver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id', 'approver_id', name='uq_transaction_approver')
    )
    op.create_index(op.f('ix_pending_transaction_approval_votes_id'), 'pending_transaction_approval_votes', ['id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_pending_transaction_approval_votes_id'), table_name='pending_transaction_approval_votes')
    op.drop_table('pending_transaction_approval_votes')
    op.drop_index(op.f('ix_pending_transaction_approvals_id'), table_name='pending_transaction_approvals')
    op.drop_table('pending_transaction_approvals')
