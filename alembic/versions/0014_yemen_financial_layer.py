"""Yemen financial-layer primitives: money-unit variants and scoped FX observations."""
from alembic import op
import sqlalchemy as sa

revision = "0014_yemen_financial_layer"
down_revision = "0013_ai_product_lock"
branch_labels = None
depends_on = None


def upgrade():
    # The canonical baseline is model-driven: 0001 creates Base.metadata, so
    # these tables already exist on fresh canonical databases. This revision
    # records the financial-layer schema boundary without duplicating DDL.
    pass


def downgrade():
    op.drop_index("ix_market_fx_lookup", table_name="market_exchange_rates")
    op.drop_table("market_exchange_rates")
    op.drop_table("market_money_units")
