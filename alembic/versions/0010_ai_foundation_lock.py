"""AI-01 governed intelligence foundation lock.

The repository uses a model-driven 0001 baseline.  This migration therefore
closes the AI-01 schema conditionally so fresh baseline databases and upgrades
from 0009 converge on the same schema.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_ai_foundation_lock"
down_revision = "0009_marketplace_lifecycle_financial_isolation"
branch_labels = None
depends_on = None


def _table_names(bind):
    return set(sa.inspect(bind).get_table_names())


def _add_column_if_missing(bind, table, column):
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if column.name not in cols:
        op.add_column(table, column)


def _create_if_missing(bind, table_name, *columns, indexes=(), constraints=()):
    if table_name in _table_names(bind):
        return
    op.create_table(table_name, *columns, *constraints)
    for name, cols in indexes:
        op.create_index(name, table_name, cols)


def upgrade():
    bind = op.get_bind()
    _add_column_if_missing(bind, "ai_tool_definitions", sa.Column("side_effect_class", sa.String(30), nullable=False, server_default="read"))
    _add_column_if_missing(bind, "ai_tool_definitions", sa.Column("data_classification", sa.JSON(), nullable=False, server_default="[]"))
    _add_column_if_missing(bind, "ai_tool_definitions", sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_column_if_missing(bind, "ai_tool_definitions", sa.Column("idempotency_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing(bind, "ai_tool_definitions", sa.Column("handler_key", sa.String(160), nullable=True))

    _create_if_missing(bind, "ai_provider_configs",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(120), nullable=False), sa.Column("provider_kind", sa.String(40), nullable=False), sa.Column("endpoint_ref", sa.String(500)),
        sa.Column("credential_ref", sa.String(255)), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("privacy_class", sa.String(30), nullable=False, server_default="standard"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        indexes=(("ix_ai_provider_configs_tenant_id", ["tenant_id"]),), constraints=(sa.UniqueConstraint("tenant_id", "code", name="uq_ai_provider_tenant_code"),))

    _create_if_missing(bind, "ai_model_routes",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_code", sa.String(120), nullable=False), sa.Column("provider_code", sa.String(120), nullable=False), sa.Column("model_code", sa.String(160), nullable=False),
        sa.Column("task_class", sa.String(60), nullable=False), sa.Column("priority", sa.Integer(), nullable=False, server_default="100"), sa.Column("max_input_tokens", sa.Integer()),
        sa.Column("structured_output", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("tool_calling", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("policy", sa.JSON(), nullable=False, server_default="{}"),
        indexes=(("ix_ai_model_routes_tenant_id", ["tenant_id"]),), constraints=(sa.UniqueConstraint("tenant_id", "route_code", name="uq_ai_route_tenant_code"),))

    _create_if_missing(bind, "ai_agent_definitions",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(120), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("role", sa.String(80), nullable=False),
        sa.Column("system_policy", sa.Text(), nullable=False), sa.Column("scopes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("tool_codes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("data_classes", sa.JSON(), nullable=False, server_default="[]"), sa.Column("risk_class", sa.String(30), nullable=False, server_default="low"),
        sa.Column("approval_mode", sa.String(30), nullable=False, server_default="human_required"), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        indexes=(("ix_ai_agent_definitions_tenant_id", ["tenant_id"]),), constraints=(sa.UniqueConstraint("tenant_id", "code", name="uq_ai_agent_tenant_code"),))

    _create_if_missing(bind, "ai_memory_records",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(255)), sa.Column("agent_code", sa.String(120)), sa.Column("memory_type", sa.String(40), nullable=False), sa.Column("key", sa.String(180), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False, server_default="{}"), sa.Column("source", sa.String(40), nullable=False), sa.Column("trust", sa.String(20), nullable=False, server_default="unverified"),
        sa.Column("revocable", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        indexes=(("ix_ai_memory_records_tenant_id", ["tenant_id"]),("ix_ai_memory_records_owner_id", ["owner_id"]),("ix_ai_memory_records_agent_code", ["agent_code"]),("ix_ai_memory_scope", ["tenant_id","owner_id","agent_code","memory_type","key"])))

    _create_if_missing(bind, "ai_trace_events",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False), sa.Column("stage", sa.String(50), nullable=False), sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False, server_default="{}"), sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        indexes=(("ix_ai_trace_events_tenant_id", ["tenant_id"]),("ix_ai_trace_events_run_id", ["run_id"]),("ix_ai_trace_run_stage", ["run_id","stage","created_at"])))

    _create_if_missing(bind, "ai_usage_events",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False), sa.Column("provider_code", sa.String(120)), sa.Column("model_code", sa.String(160)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"), sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("latency_ms", sa.Integer()), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        indexes=(("ix_ai_usage_events_tenant_id", ["tenant_id"]),("ix_ai_usage_events_run_id", ["run_id"])))


def downgrade():
    bind = op.get_bind()
    for table in ["ai_usage_events", "ai_trace_events", "ai_memory_records", "ai_agent_definitions", "ai_model_routes", "ai_provider_configs"]:
        if table in _table_names(bind): op.drop_table(table)
    cols = {c["name"] for c in sa.inspect(bind).get_columns("ai_tool_definitions")}
    for name in ["handler_key", "idempotency_required", "approval_required", "data_classification", "side_effect_class"]:
        if name in cols: op.drop_column("ai_tool_definitions", name)
