"""add governed market capability activation"""
from alembic import op
import sqlalchemy as sa

revision = "0032_market_capability_activation"
down_revision = "0031_platform_capability_registry"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if "market_capability_activations" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "market_capability_activations",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_id", sa.String(80), sa.ForeignKey("platform_capabilities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("activated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_id", "capability_id", name="uq_market_capability_activation"),
        sa.CheckConstraint("status IN ('active','suspended')", name="ck_market_capability_activation_status"),
    )

def downgrade():
    op.drop_table("market_capability_activations")
