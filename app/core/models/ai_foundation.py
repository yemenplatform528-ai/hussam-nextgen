"""AI-01 governed intelligence-plane persistence models.

These models store configuration and evidence for AI orchestration.  They do not
become an authority over tenant, financial, inventory, payment, or marketplace
records; domain services remain authoritative.
"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credential_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    privacy_class: Mapped[str] = mapped_column(String(30), nullable=False, default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_ai_provider_tenant_code"),)


class AIModelRoute(Base):
    __tablename__ = "ai_model_routes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    route_code: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(120), nullable=False)
    model_code: Mapped[str] = mapped_column(String(160), nullable=False)
    task_class: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    structured_output: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tool_calling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (UniqueConstraint("tenant_id", "route_code", name="uq_ai_route_tenant_code"),)


class AIAgentDefinition(Base):
    __tablename__ = "ai_agent_definitions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    system_policy: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tool_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    data_classes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risk_class: Mapped[str] = mapped_column(String(30), nullable=False, default="low")
    approval_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="human_required")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_ai_agent_tenant_code"),)


class AIMemoryRecord(Base):
    __tablename__ = "ai_memory_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    agent_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    memory_type: Mapped[str] = mapped_column(String(40), nullable=False)
    key: Mapped[str] = mapped_column(String(180), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    trust: Mapped[str] = mapped_column(String(20), nullable=False, default="unverified")
    revocable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        Index("ix_ai_memory_scope", "tenant_id", "owner_id", "agent_code", "memory_type", "key"),
    )


class AITraceEvent(Base):
    __tablename__ = "ai_trace_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (Index("ix_ai_trace_run_stage", "run_id", "stage", "created_at"),)


class AIUsageEvent(Base):
    __tablename__ = "ai_usage_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[object] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
