"""Enforce HUS execution idempotency at the persistence boundary."""
from alembic import op
import sqlalchemy as sa

revision = "0041_hus_execution_idempotency"
down_revision = "0040_hus_approval_provenance"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("hus_execution_records")}
    if "idempotency_key" not in cols:
        op.add_column("hus_execution_records", sa.Column("idempotency_key", sa.String(255), nullable=True))
    constraints = {x["name"] for x in sa.inspect(bind).get_unique_constraints("hus_execution_records")}
    if "uq_hus_execution_idempotency" not in constraints:
        op.create_unique_constraint(
            "uq_hus_execution_idempotency",
            "hus_execution_records",
            ["tenant_id", "compilation_id", "idempotency_key"],
        )


def downgrade():
    bind = op.get_bind()
    constraints = {x["name"] for x in sa.inspect(bind).get_unique_constraints("hus_execution_records")}
    if "uq_hus_execution_idempotency" in constraints:
        op.drop_constraint("uq_hus_execution_idempotency", "hus_execution_records", type_="unique")
    cols = {c["name"] for c in sa.inspect(bind).get_columns("hus_execution_records")}
    if "idempotency_key" in cols:
        op.drop_column("hus_execution_records", "idempotency_key")
