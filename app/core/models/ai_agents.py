from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class AIAgentRun(Base):
    __tablename__ = "ai_agent_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    market_id: Mapped[int | None] = mapped_column(ForeignKey("market_contexts.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    budget_agents: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    selected_agents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (Index("ix_ai_agent_runs_scope", "tenant_id", "market_id", "created_at"),)


class AIAgentDelegation(Base):
    __tablename__ = "ai_agent_delegations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ai_agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_agent_code: Mapped[str] = mapped_column(String(120), nullable=False)
    child_agent_code: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    market_id: Mapped[int | None] = mapped_column(ForeignKey("market_contexts.id", ondelete="SET NULL"), nullable=True)
    allowed_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (Index("ix_ai_agent_delegations_run_sequence", "run_id", "sequence"),
                      Index("ix_ai_agent_delegations_scope", "tenant_id", "child_agent_code", "status"))
