from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, JSON, String, Text, UniqueConstraint
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
