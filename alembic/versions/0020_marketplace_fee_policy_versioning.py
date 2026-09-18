"""version marketplace fee policies and snapshot applied terms

Revision ID: 0020_marketplace_fee_policy_versioning
Revises: 0019_marketplace_order_financial_allocations
"""
from alembic import op
import sqlalchemy as sa

revision = '0020_marketplace_fee_policy_versioning'
down_revision = '0019_marketplace_order_financial_allocations'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    fee_cols = {c['name'] for c in insp.get_columns('marketplace_fee_rules')}
    order_fee_cols = {c['name'] for c in insp.get_columns('marketplace_order_fees')}
    if 'policy_version' not in fee_cols:
        op.add_column('marketplace_fee_rules', sa.Column('policy_version', sa.String(length=80), nullable=False, server_default='v1'))
    if 'effective_from' not in fee_cols:
        op.add_column('marketplace_fee_rules', sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    if 'effective_to' not in fee_cols:
        op.add_column('marketplace_fee_rules', sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True))
    if 'ck_market_fee_rule_effective_window' not in {c['name'] for c in insp.get_check_constraints('marketplace_fee_rules')}:
        op.create_check_constraint('ck_market_fee_rule_effective_window', 'marketplace_fee_rules', 'effective_to IS NULL OR effective_to > effective_from')
    if 'policy_version' not in order_fee_cols:
        op.add_column('marketplace_order_fees', sa.Column('policy_version', sa.String(length=80), nullable=False, server_default='v1'))
    if 'policy_snapshot' not in order_fee_cols:
        op.add_column('marketplace_order_fees', sa.Column('policy_snapshot', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    op.drop_column('marketplace_order_fees', 'policy_snapshot')
    op.drop_column('marketplace_order_fees', 'policy_version')
    op.drop_constraint('ck_market_fee_rule_effective_window', 'marketplace_fee_rules', type_='check')
    op.drop_column('marketplace_fee_rules', 'effective_to')
    op.drop_column('marketplace_fee_rules', 'effective_from')
    op.drop_column('marketplace_fee_rules', 'policy_version')
