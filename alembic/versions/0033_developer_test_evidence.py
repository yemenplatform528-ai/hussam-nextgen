"""add immutable developer test evidence fields and invariant"""
from alembic import op
import sqlalchemy as sa

revision = "0033_developer_test_evidence"
down_revision = "0032_market_capability_activation"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_developer_extension_test_evidence"
TABLE = "developer_extension_versions"


def _has_column(inspector, name: str) -> bool:
    return any(column["name"] == name for column in inspector.get_columns(TABLE))


def _has_constraint(inspector) -> bool:
    return any(
        item.get("name") == CONSTRAINT
        for item in inspector.get_check_constraints(TABLE)
    )


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # The repository historically allowed Base.metadata.create_all() in test/dev
    # environments, so this migration must converge safely even when the new
    # columns already exist in a pre-created schema.
    if not _has_column(inspector, "test_evidence_hash"):
        op.add_column(TABLE, sa.Column("test_evidence_hash", sa.String(64), nullable=True))
    if not _has_column(inspector, "test_run_id"):
        op.add_column(TABLE, sa.Column("test_run_id", sa.String(120), nullable=True))
    if not _has_column(inspector, "tested_at"):
        op.add_column(TABLE, sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True))

    inspector = sa.inspect(bind)
    if _has_constraint(inspector):
        return

    condition = (
        "(test_status = 'pending') OR "
        "(test_evidence_hash IS NOT NULL AND "
        "test_run_id IS NOT NULL AND tested_at IS NOT NULL)"
    )

    if bind.dialect.name == "sqlite":
        # SQLite cannot ALTER TABLE ADD CONSTRAINT. Batch mode recreates the
        # table while preserving the existing columns/data and adds the invariant.
        with op.batch_alter_table(TABLE, recreate="always") as batch:
            batch.create_check_constraint(CONSTRAINT, condition)
    else:
        op.create_check_constraint(CONSTRAINT, TABLE, condition)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_constraint(inspector):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(TABLE, recreate="always") as batch:
                batch.drop_constraint(CONSTRAINT, type_="check")
        else:
            op.drop_constraint(CONSTRAINT, TABLE, type_="check")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "tested_at"):
        op.drop_column(TABLE, "tested_at")
    if _has_column(inspector, "test_run_id"):
        op.drop_column(TABLE, "test_run_id")
    if _has_column(inspector, "test_evidence_hash"):
        op.drop_column(TABLE, "test_evidence_hash")
