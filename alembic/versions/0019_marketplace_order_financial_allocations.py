"""Add immutable line-level multi-seller financial allocations."""
from alembic import op
import sqlalchemy as sa

revision = "0019_marketplace_order_financial_allocations"
down_revision = "0018_marketplace_refund_recovery"
branch_labels = None
depends_on = None

def _has_table(name):
    return sa.inspect(op.get_bind()).has_table(name)

def upgrade():
    if _has_table('marketplace_order_financial_allocations'):
        return
    op.create_table(
        'marketplace_order_financial_allocations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('marketplace_order_id', sa.Integer(), nullable=False),
        sa.Column('order_line_id', sa.Integer(), nullable=False),
        sa.Column('seller_order_id', sa.Integer(), nullable=False),
        sa.Column('seller_tenant_id', sa.Integer(), nullable=False),
        sa.Column('market_id', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('gross_amount', sa.Numeric(20,4), nullable=False),
        sa.Column('shipping_amount', sa.Numeric(20,4), nullable=False, server_default='0'),
        sa.Column('discount_amount', sa.Numeric(20,4), nullable=False, server_default='0'),
        sa.Column('platform_fee', sa.Numeric(20,4), nullable=False, server_default='0'),
        sa.Column('net_amount', sa.Numeric(20,4), nullable=False),
        sa.Column('allocation_reference', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['marketplace_order_id'], ['marketplace_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_line_id'], ['marketplace_order_lines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_order_id'], ['marketplace_seller_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['seller_tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['market_id'], ['market_contexts.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('gross_amount >= 0 AND shipping_amount >= 0 AND discount_amount >= 0 AND platform_fee >= 0 AND net_amount >= 0', name='ck_market_fin_alloc_nonnegative'),
        sa.CheckConstraint('discount_amount <= gross_amount + shipping_amount', name='ck_market_fin_alloc_discount_bound'),
        sa.CheckConstraint('net_amount = gross_amount + shipping_amount - discount_amount - platform_fee', name='ck_market_fin_alloc_math'),
        sa.UniqueConstraint('marketplace_order_id','order_line_id', name='uq_market_fin_alloc_order_line'),
        sa.UniqueConstraint('order_line_id', name='uq_market_fin_alloc_line'),
        sa.UniqueConstraint('allocation_reference', name='uq_market_fin_alloc_reference'),
    )
    op.create_index('ix_market_fin_alloc_seller_market_currency','marketplace_order_financial_allocations',['seller_tenant_id','market_id','currency'])

def downgrade():
    op.drop_index('ix_market_fin_alloc_seller_market_currency', table_name='marketplace_order_financial_allocations')
    op.drop_table('marketplace_order_financial_allocations')
