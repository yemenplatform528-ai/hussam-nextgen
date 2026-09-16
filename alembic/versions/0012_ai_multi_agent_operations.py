"""AI-03 bounded multi-agent operations lock."""
from alembic import op
import sqlalchemy as sa
revision = "0012_ai_multi_agent_operations"
down_revision = "0011_ai_commerce_intelligence"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "ai_agent_runs" not in tables:
        op.create_table("ai_agent_runs",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.String(255), nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("depth", sa.Integer(), nullable=False),
            sa.Column("budget_agents", sa.Integer(), nullable=False),
            sa.Column("selected_agents", sa.JSON(), nullable=False),
            sa.Column("result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_ai_agent_runs_tenant_id", "ai_agent_runs", ["tenant_id"])
        op.create_index("ix_ai_agent_runs_market_id", "ai_agent_runs", ["market_id"])
        op.create_index("ix_ai_agent_runs_scope", "ai_agent_runs", ["tenant_id", "market_id", "created_at"])
    if "ai_agent_delegations" not in tables:
        op.create_table("ai_agent_delegations",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("run_id", sa.String(64), sa.ForeignKey("ai_agent_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("parent_agent_code", sa.String(120), nullable=False),
            sa.Column("child_agent_code", sa.String(120), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("depth", sa.Integer(), nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("allowed_scopes", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_ai_agent_delegations_tenant_id", "ai_agent_delegations", ["tenant_id"])
        op.create_index("ix_ai_agent_delegations_run_id", "ai_agent_delegations", ["run_id"])
        op.create_index("ix_ai_agent_delegations_run_sequence", "ai_agent_delegations", ["run_id", "sequence"])
        op.create_index("ix_ai_agent_delegations_scope", "ai_agent_delegations", ["tenant_id", "child_agent_code", "status"])


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "ai_agent_delegations" in tables: op.drop_table("ai_agent_delegations")
    if "ai_agent_runs" in tables: op.drop_table("ai_agent_runs")
