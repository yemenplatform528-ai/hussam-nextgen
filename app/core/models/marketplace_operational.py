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
    seller_funded_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    platform_funded_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("funding_source IN ('seller','platform','shared')", name='ck_discount_funding_source'),
        CheckConstraint('amount >= 0 AND (seller_funded_amount IS NULL OR seller_funded_amount >= 0) AND (platform_funded_amount IS NULL OR platform_funded_amount >= 0)', name='ck_discount_allocation_nonnegative'),
        CheckConstraint('(seller_funded_amount IS NULL AND platform_funded_amount IS NULL) OR (seller_funded_amount IS NOT NULL AND platform_funded_amount IS NOT NULL AND seller_funded_amount + platform_funded_amount = amount)', name='ck_discount_funding_conservation'),
        CheckConstraint("funding_source != 'seller' OR (seller_funded_amount IS NULL OR seller_funded_amount = amount)", name='ck_discount_seller_funding'),
        CheckConstraint("funding_source != 'platform' OR (platform_funded_amount IS NULL OR platform_funded_amount = amount)", name='ck_discount_platform_funding'),
        UniqueConstraint('customer_order_id', 'seller_order_id', 'promotion_id', 'coupon_id', name='uq_discount_allocation_scope'),
        Index('ix_discount_allocation_order', 'customer_order_id', 'seller_tenant_id'),
    )


class MarketplaceOrderFinancialAllocation(Base):
    __tablename__ = 'marketplace_order_financial_allocations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey('marketplace_order_lines.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    seller_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_seller_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    platform_fee: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    allocation_reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint('gross_amount >= 0 AND shipping_amount >= 0 AND discount_amount >= 0 AND platform_fee >= 0 AND net_amount >= 0', name='ck_market_fin_alloc_nonnegative'),
        CheckConstraint('discount_amount <= gross_amount + shipping_amount', name='ck_market_fin_alloc_discount_bound'),
        CheckConstraint('net_amount = gross_amount + shipping_amount - discount_amount - platform_fee', name='ck_market_fin_alloc_math'),
        UniqueConstraint('marketplace_order_id', 'order_line_id', name='uq_market_fin_alloc_order_line'),
        Index('ix_market_fin_alloc_seller_market_currency', 'seller_tenant_id', 'market_id', 'currency'),
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
