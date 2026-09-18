"""snapshot seller/platform funded discount on seller payout"""
from alembic import op
import sqlalchemy as sa

revision = '0025_payout_discount_funding'
down_revision = '0024_discount_funding_scope'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('marketplace_payouts')}
    if 'seller_funded_discount' not in cols:
        op.add_column('marketplace_payouts', sa.Column('seller_funded_discount', sa.Numeric(20, 4), nullable=False, server_default='0'))
    if 'platform_funded_discount' not in cols:
        op.add_column('marketplace_payouts', sa.Column('platform_funded_discount', sa.Numeric(20, 4), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('marketplace_payouts', 'platform_funded_discount')
    op.drop_column('marketplace_payouts', 'seller_funded_discount')
