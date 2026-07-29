"""Add processed_transactions table (duplicate message detection)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-23 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'processed_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mt_type', sa.String(), nullable=False),
        sa.Column('reference', sa.String(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_processed_transactions_id'), 'processed_transactions', ['id'])
    op.create_index(op.f('ix_processed_transactions_mt_type'), 'processed_transactions', ['mt_type'])
    op.create_index(op.f('ix_processed_transactions_reference'), 'processed_transactions', ['reference'])
    op.create_index(op.f('ix_processed_transactions_created_at'), 'processed_transactions', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_processed_transactions_created_at'), table_name='processed_transactions')
    op.drop_index(op.f('ix_processed_transactions_reference'), table_name='processed_transactions')
    op.drop_index(op.f('ix_processed_transactions_mt_type'), table_name='processed_transactions')
    op.drop_index(op.f('ix_processed_transactions_id'), table_name='processed_transactions')
    op.drop_table('processed_transactions')
