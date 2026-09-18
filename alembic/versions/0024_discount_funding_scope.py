"""record seller/platform funding split for marketplace discounts"""
from alembic import op
import sqlalchemy as sa

revision = '0024_discount_funding_scope'
down_revision = '0023_payout_destination_snapshot'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('marketplace_discount_allocations')}
    if 'seller_funded_amount' not in cols:
        op.add_column('marketplace_discount_allocations', sa.Column('seller_funded_amount', sa.Numeric(20, 4), nullable=True))
    if 'platform_funded_amount' not in cols:
        op.add_column('marketplace_discount_allocations', sa.Column('platform_funded_amount', sa.Numeric(20, 4), nullable=True))

def downgrade():
    op.drop_column('marketplace_discount_allocations', 'platform_funded_amount')
    op.drop_column('marketplace_discount_allocations', 'seller_funded_amount')
