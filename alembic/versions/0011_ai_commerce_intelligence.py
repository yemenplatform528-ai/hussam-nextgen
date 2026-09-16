"""AI-02 governed commerce intelligence lock."""
from alembic import op
import sqlalchemy as sa
revision = "0011_ai_commerce_intelligence"
down_revision = "0010_ai_foundation_lock"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if "ai_commerce_signals" not in sa.inspect(bind).get_table_names():
        op.create_table("ai_commerce_signals",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.String(255), nullable=False),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="SET NULL")),
            sa.Column("kind", sa.String(80), nullable=False), sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_ai_commerce_signals_tenant_id", "ai_commerce_signals", ["tenant_id"])
        op.create_index("ix_ai_commerce_signals_market_id", "ai_commerce_signals", ["market_id"])
        op.create_index("ix_ai_commerce_signal_scope", "ai_commerce_signals", ["tenant_id","market_id","kind","created_at"])

def downgrade():
    bind = op.get_bind()
    if "ai_commerce_signals" in sa.inspect(bind).get_table_names(): op.drop_table("ai_commerce_signals")
