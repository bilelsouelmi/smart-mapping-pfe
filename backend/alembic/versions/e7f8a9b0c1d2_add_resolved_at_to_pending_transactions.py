"""Add resolved_at to pending_transaction_approvals

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-23 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'd6e7f8a9b0c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('pending_transaction_approvals', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('pending_transaction_approvals', 'resolved_at')
