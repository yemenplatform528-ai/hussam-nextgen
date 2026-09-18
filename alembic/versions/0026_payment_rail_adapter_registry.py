"""add governed payment rail and adapter registries"""
from alembic import op
import sqlalchemy as sa

revision = '0026_payment_rail_adapter_registry'
down_revision = '0025_payout_discount_funding'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'payment_rail_registry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market_id', sa.Integer(), sa.ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(80), nullable=False),
        sa.Column('capability', sa.String(80), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False, server_default=''),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.UniqueConstraint('market_id', 'code', name='uq_payment_rail_market_code'),
        sa.CheckConstraint("status IN ('draft','certified','production','suspended','retired')", name='ck_payment_rail_status'),
    )
    op.create_table(
        'payment_adapter_registry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('provider_registry_entries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rail_id', sa.Integer(), sa.ForeignKey('payment_rail_registry.id', ondelete='CASCADE'), nullable=False),
        sa.Column('adapter_code', sa.String(120), nullable=False),
        sa.Column('adapter_version', sa.String(40), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.UniqueConstraint('provider_id','rail_id','adapter_code','adapter_version', name='uq_payment_adapter_registry_identity'),
        sa.CheckConstraint("status IN ('pending','testing','certified','production','suspended','retired')", name='ck_payment_adapter_registry_status'),
    )
    op.create_index('ix_payment_adapter_registry_provider_rail', 'payment_adapter_registry', ['provider_id','rail_id'])

def downgrade():
    op.drop_index('ix_payment_adapter_registry_provider_rail', table_name='payment_adapter_registry')
    op.drop_table('payment_adapter_registry')
    op.drop_table('payment_rail_registry')
