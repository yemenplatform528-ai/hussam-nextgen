"""track settlement reconciliation state"""
from alembic import op
import sqlalchemy as sa

revision = '0027_settlement_reconciliation_state'
down_revision = '0026_payment_rail_adapter_registry'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('payment_settlements')}
    checks = {c['name'] for c in insp.get_check_constraints('payment_settlements')}
    if 'reconciliation_status' not in cols:
        op.add_column('payment_settlements', sa.Column('reconciliation_status', sa.String(20), nullable=False, server_default='pending'))
    if 'reconciliation_run_reference' not in cols:
        op.add_column('payment_settlements', sa.Column('reconciliation_run_reference', sa.String(255), nullable=True))
    if 'ck_payment_settlement_reconciliation_status' not in checks:
        op.create_check_constraint(
            'ck_payment_settlement_reconciliation_status',
            'payment_settlements',
            "reconciliation_status IN ('pending','reconciled','exception')",
        )

def downgrade():
    op.drop_constraint('ck_payment_settlement_reconciliation_status', 'payment_settlements', type_='check')
    op.drop_column('payment_settlements', 'reconciliation_run_reference')
    op.drop_column('payment_settlements', 'reconciliation_status')
