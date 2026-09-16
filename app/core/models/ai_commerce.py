from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Index, JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class AICommerceSignal(Base):
    __tablename__ = "ai_commerce_signals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    market_id: Mapped[int | None] = mapped_column(ForeignKey("market_contexts.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (Index("ix_ai_commerce_signal_scope", "tenant_id", "market_id", "kind", "created_at"),)
