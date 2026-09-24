from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class PlatformCapability(Base):
    """Governed capability catalog consumed by the Developer Platform."""
    __tablename__ = "platform_capabilities"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    market_scope: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint("category", "code", name="uq_platform_capability_category_code"),
        CheckConstraint("status IN ('active','draft','deprecated','suspended')", name="ck_platform_capability_status"),
    )


class MarketCapabilityActivation(Base):
    """Market-scoped activation of a governed platform capability."""
    __tablename__ = "market_capability_activations"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    capability_id: Mapped[str] = mapped_column(ForeignKey("platform_capabilities.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Actor identity follows the platform's User.id contract (string), not Tenant.id (integer).
    activated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint("market_id", "capability_id", name="uq_market_capability_activation"),
        CheckConstraint("status IN ('active','suspended')", name="ck_market_capability_activation_status"),
    )
