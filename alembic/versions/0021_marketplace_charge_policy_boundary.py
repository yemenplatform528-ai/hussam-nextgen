"""establish neutral tax and regulatory charge policy boundary"""
from alembic import op
import sqlalchemy as sa
revision='0021_marketplace_charge_policy_boundary'
down_revision='0020_marketplace_fee_policy_versioning'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind(); insp=sa.inspect(bind); tables=set(insp.get_table_names())
    if 'marketplace_charge_rules' not in tables:
        op.create_table('marketplace_charge_rules',
            sa.Column('id',sa.Integer(),primary_key=True),
            sa.Column('market_id',sa.Integer(),sa.ForeignKey('market_contexts.id',ondelete='CASCADE'),nullable=True,index=True),
            sa.Column('name',sa.String(160),nullable=False), sa.Column('charge_type',sa.String(40),nullable=False),
            sa.Column('jurisdiction_code',sa.String(80),nullable=True), sa.Column('rate_bps',sa.Integer(),nullable=False,server_default='0'),
            sa.Column('fixed_amount',sa.Numeric(20,4),nullable=False,server_default='0'), sa.Column('currency',sa.String(10),nullable=True),
            sa.Column('priority',sa.Integer(),nullable=False,server_default='100'), sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('policy_version',sa.String(80),nullable=False,server_default='v1'),
            sa.Column('effective_from',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('effective_to',sa.DateTime(timezone=True),nullable=True), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.CheckConstraint("charge_type IN ('tax','regulatory_fee','levy')",name='ck_market_charge_rule_type'),
            sa.CheckConstraint('rate_bps >= 0 AND rate_bps <= 10000',name='ck_market_charge_rule_bps'),
            sa.CheckConstraint('fixed_amount >= 0',name='ck_market_charge_rule_fixed_nonnegative'),
            sa.CheckConstraint('effective_to IS NULL OR effective_to > effective_from',name='ck_market_charge_rule_effective_window'))
    if 'marketplace_order_charges' not in tables:
        op.create_table('marketplace_order_charges',
            sa.Column('id',sa.Integer(),primary_key=True), sa.Column('marketplace_order_id',sa.Integer(),sa.ForeignKey('marketplace_orders.id',ondelete='CASCADE'),nullable=False,index=True),
            sa.Column('seller_tenant_id',sa.Integer(),sa.ForeignKey('tenants.id',ondelete='RESTRICT'),nullable=False,index=True), sa.Column('rule_id',sa.Integer(),sa.ForeignKey('marketplace_charge_rules.id',ondelete='SET NULL'),nullable=True),
            sa.Column('charge_type',sa.String(40),nullable=False), sa.Column('jurisdiction_code',sa.String(80),nullable=True), sa.Column('basis_amount',sa.Numeric(20,4),nullable=False),
            sa.Column('rate_bps',sa.Integer(),nullable=False), sa.Column('fixed_amount',sa.Numeric(20,4),nullable=False,server_default='0'), sa.Column('amount',sa.Numeric(20,4),nullable=False),
            sa.Column('currency',sa.String(10),nullable=False), sa.Column('policy_version',sa.String(80),nullable=False), sa.Column('policy_snapshot',sa.JSON(),nullable=False,server_default='{}'),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.CheckConstraint("charge_type IN ('tax','regulatory_fee','levy')",name='ck_market_order_charge_type'),
            sa.CheckConstraint('basis_amount >= 0 AND rate_bps >= 0 AND fixed_amount >= 0 AND amount >= 0',name='ck_market_order_charge_amounts'),
            sa.UniqueConstraint('marketplace_order_id','charge_type','jurisdiction_code','policy_version',name='uq_market_order_charge_policy'))

def downgrade():
    op.drop_table('marketplace_order_charges'); op.drop_table('marketplace_charge_rules')
