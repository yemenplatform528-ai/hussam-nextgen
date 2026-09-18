"""Payment reconciliation run boundary.

The canonical project is model-driven on fresh databases; 0001 creates
Base.metadata. This revision records the schema boundary without duplicating
DDL, consistent with the financial-layer migration pattern.
"""
from alembic import op

revision = "0015_payment_reconciliation_runs"
down_revision = "0014_yemen_financial_layer"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
