"""store the selected marketplace payment method on customer and seller orders"""
from alembic import op
import sqlalchemy as sa

revision = "0035_marketplace_payment_method"
down_revision = "0034_test_evidence_source_binding"
branch_labels = None
depends_on = None

TABLES = ("marketplace_customer_orders", "marketplace_orders")
COLUMN = "payment_method_code"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        if not any(c["name"] == COLUMN for c in inspector.get_columns(table)):
            op.add_column(table, sa.Column(COLUMN, sa.String(40), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in reversed(TABLES):
        if any(c["name"] == COLUMN for c in inspector.get_columns(table)):
            op.drop_column(table, COLUMN)
