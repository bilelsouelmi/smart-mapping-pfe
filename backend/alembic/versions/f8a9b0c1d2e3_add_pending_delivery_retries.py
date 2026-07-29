"""Add pending_delivery_retries table

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-07-24 00:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pending_delivery_retries',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('pipeline_id', sa.Integer(), sa.ForeignKey('config_consommations.id'), nullable=True),
        sa.Column('pipeline_name', sa.String(), nullable=False),
        sa.Column('config_out_id', sa.Integer(), sa.ForeignKey('transport_configs.id'), nullable=True),
        sa.Column('transport_type', sa.String(), nullable=False),
        sa.Column('output_filename', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('pending_delivery_retries')
