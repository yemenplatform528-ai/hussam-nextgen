from alembic import op
import sqlalchemy as sa

revision = "0033_developer_test_evidence"
down_revision = "0032_market_capability_activation"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("developer_extension_versions", sa.Column("test_evidence_hash", sa.String(64), nullable=True))
    op.add_column("developer_extension_versions", sa.Column("test_run_id", sa.String(120), nullable=True))
    op.add_column("developer_extension_versions", sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_developer_extension_test_evidence",
        "developer_extension_versions",
        "(test_status = 'pending') OR (test_evidence_hash IS NOT NULL AND test_run_id IS NOT NULL AND tested_at IS NOT NULL)",
    )

def downgrade():
    op.drop_constraint("ck_developer_extension_test_evidence", "developer_extension_versions", type_="check")
    op.drop_column("developer_extension_versions", "tested_at")
    op.drop_column("developer_extension_versions", "test_run_id")
    op.drop_column("developer_extension_versions", "test_evidence_hash")
