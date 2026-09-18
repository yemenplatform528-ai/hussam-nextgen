"""Allow post-payout refund recovery against seller balance."""
from alembic import op

revision = "0018_marketplace_refund_recovery"
down_revision = "0017_marketplace_seller_balance_ledger"
branch_labels = None
depends_on = None

_NEW = "entry_type IN ('credit','debit','refund_reversal','refund_recovery','payout_debit')"
_OLD = "entry_type IN ('credit','debit','refund_reversal','payout_debit')"

def upgrade():
    with op.batch_alter_table('marketplace_seller_balance_entries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_market_seller_balance_entry_type', type_='check')
        batch_op.create_check_constraint('ck_market_seller_balance_entry_type', _NEW)

def downgrade():
    with op.batch_alter_table('marketplace_seller_balance_entries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_market_seller_balance_entry_type', type_='check')
        batch_op.create_check_constraint('ck_market_seller_balance_entry_type', _OLD)
