"""Add approver_role + pending_reason to pending_transaction_approvals (PEP holds)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-23 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('pending_transaction_approvals', sa.Column('approver_role', sa.String(), server_default='admin', nullable=False))
    op.add_column('pending_transaction_approvals', sa.Column('pending_reason', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('pending_transaction_approvals', 'pending_reason')
    op.drop_column('pending_transaction_approvals', 'approver_role')
