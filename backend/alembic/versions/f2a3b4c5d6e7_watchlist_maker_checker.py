"""Rework watchlist_entities for maker-checker (status/proposed_by/reviewed_by)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-22 16:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('watchlist_entities')
    op.create_table(
        'watchlist_entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('list_type', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('proposed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['proposed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_watchlist_entities_id'), 'watchlist_entities', ['id'])
    op.create_index(op.f('ix_watchlist_entities_name'), 'watchlist_entities', ['name'])


def downgrade() -> None:
    op.drop_index(op.f('ix_watchlist_entities_name'), table_name='watchlist_entities')
    op.drop_index(op.f('ix_watchlist_entities_id'), table_name='watchlist_entities')
    op.drop_table('watchlist_entities')
