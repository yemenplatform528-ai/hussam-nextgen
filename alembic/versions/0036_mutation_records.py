"""add explicit mutation lifecycle records"""
from alembic import op
import sqlalchemy as sa

revision = "0036_mutation_records"
down_revision = "0035_marketplace_payment_method"
branch_labels = None
depends_on = None


def upgrade():
    # The canonical 0001 baseline creates the current SQLAlchemy metadata.
    # Therefore newly introduced model tables may already exist on a fresh
    # baseline migration. Keep this revision additive for databases that were
    # genuinely upgraded from 0035 without the table.
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("mutation_records"):
        return

    op.create_table(
        "mutation_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("operation", sa.String(120), nullable=False),
        sa.Column("mutation_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(128), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resource_type", sa.String(120), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "mutation_key", name="uq_mutation_tenant_key"),
        sa.CheckConstraint(
            "state IN ('draft','pending','confirmed','failed','conflict')",
            name="ck_mutation_state",
        ),
    )
    op.create_index("ix_mutation_records_tenant_id", "mutation_records", ["tenant_id"])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("mutation_records"):
        return
    if any(i["name"] == "ix_mutation_records_tenant_id" for i in inspector.get_indexes("mutation_records")):
        op.drop_index("ix_mutation_records_tenant_id", table_name="mutation_records")
    op.drop_table("mutation_records")
