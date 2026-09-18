"""Bind payment settlement and reconciliation runs to market/currency context."""
from alembic import op
import sqlalchemy as sa

revision = '0022_payment_market_settlement_boundary'
down_revision = '0021_marketplace_charge_policy_boundary'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'payment_settlements' in insp.get_table_names():
        cols = {c['name'] for c in insp.get_columns('payment_settlements')}
        if 'market_id' not in cols:
            op.add_column('payment_settlements', sa.Column('market_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_payment_settlements_market', 'payment_settlements', 'market_contexts', ['market_id'], ['id'], ondelete='RESTRICT')
    if 'payment_reconciliation_runs' in insp.get_table_names():
        cols = {c['name'] for c in insp.get_columns('payment_reconciliation_runs')}
        if 'market_id' not in cols:
            op.add_column('payment_reconciliation_runs', sa.Column('market_id', sa.Integer(), nullable=True))
            op.add_column('payment_reconciliation_runs', sa.Column('currency', sa.String(10), nullable=True))
            op.create_foreign_key('fk_payment_recon_runs_market', 'payment_reconciliation_runs', 'market_contexts', ['market_id'], ['id'], ondelete='RESTRICT')

def downgrade():
    bind = op.get_bind(); insp = sa.inspect(bind)
    if 'payment_reconciliation_runs' in insp.get_table_names():
        op.drop_constraint('fk_payment_recon_runs_market', 'payment_reconciliation_runs', type_='foreignkey')
        op.drop_column('payment_reconciliation_runs', 'currency')
        op.drop_column('payment_reconciliation_runs', 'market_id')
    if 'payment_settlements' in insp.get_table_names():
        op.drop_constraint('fk_payment_settlements_market', 'payment_settlements', type_='foreignkey')
        op.drop_column('payment_settlements', 'market_id')
