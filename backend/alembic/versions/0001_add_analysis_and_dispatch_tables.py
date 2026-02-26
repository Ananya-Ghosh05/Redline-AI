"""Add analysis_results and dispatch_recommendations tables

Revision ID: 0001_add_analysis_and_dispatch_tables
Revises: 
Create Date: 2026-02-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '0001_add_analysis_and_dispatch_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'analysis_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('call_id', UUID(as_uuid=True), sa.ForeignKey('calls.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('incident_type', sa.String(), nullable=False),
        sa.Column('panic_score', sa.Float(), nullable=False),
        sa.Column('keyword_score', sa.Float(), nullable=False),
        sa.Column('severity_prediction', sa.String(), nullable=True),
        sa.Column('location_text', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('geo_confidence', sa.Float(), nullable=True),
    )
    op.create_table(
        'dispatch_recommendations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('call_id', UUID(as_uuid=True), sa.ForeignKey('calls.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('unit_id', sa.String(), nullable=False),
        sa.Column('eta_minutes', sa.Float(), nullable=True),
        sa.Column('priority', sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table('dispatch_recommendations')
    op.drop_table('analysis_results')

