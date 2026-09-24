"""bind developer test evidence to the exact source revision tested"""
from alembic import op
import sqlalchemy as sa

revision = "0034_test_evidence_source_binding"
down_revision = "0033_developer_test_evidence"
branch_labels = None
depends_on = None

TABLE = "developer_extension_versions"
COLUMN = "test_source_hash"

def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not any(c["name"] == COLUMN for c in inspector.get_columns(TABLE)):
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(64), nullable=True))

def downgrade():
    inspector = sa.inspect(op.get_bind())
    if any(c["name"] == COLUMN for c in inspector.get_columns(TABLE)):
        op.drop_column(TABLE, COLUMN)
