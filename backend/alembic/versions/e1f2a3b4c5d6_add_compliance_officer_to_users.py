"""Add is_compliance_officer to users (dual-control role for watchlist maker-checker)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-22 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_compliance_officer', sa.Boolean(), server_default='false', nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'is_compliance_officer')
