"""snapshot payout destination at request time

Revision ID: 0023_payout_destination_snapshot
Revises: 0022_payment_market_settlement_boundary
"""
from alembic import op
import sqlalchemy as sa

revision = '0023_payout_destination_snapshot'
down_revision = '0022_payment_market_settlement_boundary'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('marketplace_payouts', sa.Column('payout_destination_reference', sa.String(length=255), nullable=True))

def downgrade():
    op.drop_column('marketplace_payouts', 'payout_destination_reference')
