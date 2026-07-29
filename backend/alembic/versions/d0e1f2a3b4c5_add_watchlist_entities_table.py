"""Add watchlist_entities table (sanctions/PEP screening data)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-22 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'watchlist_entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('list_type', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['added_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_watchlist_entities_id'), 'watchlist_entities', ['id'])
    op.create_index(op.f('ix_watchlist_entities_name'), 'watchlist_entities', ['name'])


def downgrade() -> None:
    op.drop_index(op.f('ix_watchlist_entities_name'), table_name='watchlist_entities')
    op.drop_index(op.f('ix_watchlist_entities_id'), table_name='watchlist_entities')
    op.drop_table('watchlist_entities')
