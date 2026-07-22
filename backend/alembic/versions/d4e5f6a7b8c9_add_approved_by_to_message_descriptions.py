"""Add approved_by to message_descriptions (maker-checker)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-21 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('message_descriptions', sa.Column('approved_by', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_message_descriptions_approved_by_users',
        'message_descriptions', 'users',
        ['approved_by'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_message_descriptions_approved_by_users', 'message_descriptions', type_='foreignkey')
    op.drop_column('message_descriptions', 'approved_by')
