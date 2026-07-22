"""Widen validation_rules.field_tag to fit deep XML paths

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-19 16:52:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('validation_rules', 'field_tag',
                     existing_type=sa.String(length=50),
                     type_=sa.String(length=255))


def downgrade() -> None:
    op.alter_column('validation_rules', 'field_tag',
                     existing_type=sa.String(length=255),
                     type_=sa.String(length=50))
