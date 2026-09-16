from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc(): return datetime.now(timezone.utc)


class MarketplaceDiscountAllocation(Base):
    __tablename__ = 'marketplace_discount_allocations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_customer_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_seller_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    promotion_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_promotions.id', ondelete='SET NULL'), nullable=True, index=True)
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_coupons.id', ondelete='SET NULL'), nullable=True, index=True)
    funding_source: Mapped[str] = mapped_column(String(30), nullable=False, default='seller')
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("funding_source IN ('seller','platform','shared')", name='ck_discount_funding_source'),
        CheckConstraint('amount >= 0', name='ck_discount_allocation_nonnegative'),
        UniqueConstraint('customer_order_id', 'seller_order_id', 'promotion_id', 'coupon_id', name='uq_discount_allocation_scope'),
        Index('ix_discount_allocation_order', 'customer_order_id', 'seller_tenant_id'),
    )


class MarketplaceRepricingJob(Base):
    __tablename__ = 'marketplace_repricing_jobs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='CASCADE'), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_pricing_rules.id', ondelete='SET NULL'), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='queued')
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name='ck_repricing_job_status'),
        CheckConstraint('attempts >= 0', name='ck_repricing_job_attempts'),
    )
