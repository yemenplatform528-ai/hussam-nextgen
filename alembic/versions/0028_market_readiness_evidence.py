"""add auditable market readiness evidence register"""
from alembic import op
import sqlalchemy as sa

revision = '0028_market_readiness_evidence'
down_revision = '0027_settlement_reconciliation_state'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'market_readiness_evidence',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requirement_key', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='proposed'),
        sa.Column('source_name', sa.String(200), nullable=True),
        sa.Column('source_uri', sa.String(1000), nullable=True),
        sa.Column('source_sha256', sa.String(64), nullable=True),
        sa.Column('license_name', sa.String(200), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_reference', sa.String(200), nullable=True),
        sa.Column('acceptance_reference', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=False, server_default=''),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('market_id', 'requirement_key', 'source_sha256', name='uq_market_readiness_evidence_source'),
        sa.CheckConstraint("status IN ('proposed','reviewed','accepted','rejected','superseded')", name='ck_market_readiness_evidence_status'),
    )
    op.create_index('ix_market_readiness_evidence_market_requirement', 'market_readiness_evidence', ['market_id', 'requirement_key', 'status'])


def downgrade():
    op.drop_index('ix_market_readiness_evidence_market_requirement', table_name='market_readiness_evidence')
    op.drop_table('market_readiness_evidence')
