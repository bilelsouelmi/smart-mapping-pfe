"""Add source_file_type to validation_rules

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('validation_rules', sa.Column('source_file_type', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_validation_rules_source_file_type'), 'validation_rules', ['source_file_type'])


def downgrade() -> None:
    op.drop_index(op.f('ix_validation_rules_source_file_type'), table_name='validation_rules')
    op.drop_column('validation_rules', 'source_file_type')
