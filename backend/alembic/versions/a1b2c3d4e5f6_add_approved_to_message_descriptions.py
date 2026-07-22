"""Add approved flag to message_descriptions

Revision ID: a1b2c3d4e5f6
Revises: 204cb17928d1
Create Date: 2026-07-18 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '204cb17928d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('message_descriptions', sa.Column('approved', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('message_descriptions', 'approved')
