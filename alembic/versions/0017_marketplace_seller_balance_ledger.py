"""Seller balance ledger for marketplace payouts."""
from alembic import op
import sqlalchemy as sa


def _has_table(name):
    return sa.inspect(op.get_bind()).has_table(name)

revision = "0017_marketplace_seller_balance_ledger"
down_revision = "0016_marketplace_payout_orchestration"
branch_labels = None
depends_on = None

def upgrade():
    if _has_table('marketplace_seller_balance_entries'):
        return
    op.create_table(
        'marketplace_seller_balance_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market_id', sa.Integer(), nullable=True),
        sa.Column('seller_tenant_id', sa.Integer(), nullable=False),
        sa.Column('marketplace_payout_id', sa.Integer(), nullable=False),
        sa.Column('entry_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(20,4), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('reference', sa.String(length=255), nullable=False),
        sa.Column('source_reference', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['market_id'], ['market_contexts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['seller_tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['marketplace_payout_id'], ['marketplace_payouts.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("entry_type IN ('credit','debit','refund_reversal','payout_debit')", name='ck_market_seller_balance_entry_type'),
        sa.CheckConstraint('amount > 0', name='ck_market_seller_balance_entry_amount_positive'),
        sa.UniqueConstraint('reference', name='uq_market_seller_balance_reference'),
        sa.UniqueConstraint('marketplace_payout_id','entry_type','source_reference', name='uq_market_seller_balance_source'),
    )
    op.create_index('ix_market_seller_balance_market','marketplace_seller_balance_entries','market_id')
    op.create_index('ix_market_seller_balance_seller','marketplace_seller_balance_entries','seller_tenant_id')
    op.create_index('ix_market_seller_balance_payout','marketplace_seller_balance_entries','marketplace_payout_id')

def downgrade():
    op.drop_index('ix_market_seller_balance_payout', table_name='marketplace_seller_balance_entries')
    op.drop_index('ix_market_seller_balance_seller', table_name='marketplace_seller_balance_entries')
    op.drop_index('ix_market_seller_balance_market', table_name='marketplace_seller_balance_entries')
    op.drop_table('marketplace_seller_balance_entries')
