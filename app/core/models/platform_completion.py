from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc():
    return datetime.now(timezone.utc)

class MarketplaceCoupon(Base):
    __tablename__ = 'marketplace_coupons'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    minimum_subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_buyer_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('seller_tenant_id', 'code', name='uq_coupon_seller_code'),
        CheckConstraint("kind IN ('percentage','fixed')", name='ck_coupon_kind'),
        CheckConstraint('value >= 0 AND minimum_subtotal >= 0 AND per_buyer_limit > 0', name='ck_coupon_values'),
    )

class MarketplaceCouponRedemption(Base):
    __tablename__ = 'marketplace_coupon_redemptions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(ForeignKey('marketplace_coupons.id', ondelete='RESTRICT'), nullable=False, index=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='RESTRICT'), nullable=False, index=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('coupon_id', 'buyer_user_id', 'marketplace_order_id', name='uq_coupon_redemption_order'), CheckConstraint('discount_amount >= 0', name='ck_coupon_discount_nonnegative'))

class MarketplacePriceDecision(Base):
    __tablename__ = 'marketplace_price_decisions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='CASCADE'), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    proposed_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    floor_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    ceiling_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_pricing_rules.id', ondelete='SET NULL'), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default='')
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='accepted')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint('proposed_price >= 0', name='ck_price_decision_nonnegative'),)

class MarketplaceAdEvent(Base):
    __tablename__ = 'marketplace_ad_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('marketplace_ad_campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    ad_group_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_ad_groups.id', ondelete='SET NULL'), nullable=True, index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='SET NULL'), nullable=True, index=True)
    buyer_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    attribution_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint("event_type IN ('impression','click','conversion')", name='ck_ad_event_type'), CheckConstraint('cost >= 0', name='ck_ad_event_cost'))

class MarketplaceAdCharge(Base):
    __tablename__ = 'marketplace_ad_charges'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('marketplace_ad_campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('marketplace_ad_events.id', ondelete='RESTRICT'), nullable=False, unique=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint('amount >= 0', name='ck_ad_charge_amount'),)

class MarketplaceAdAttribution(Base):
    __tablename__ = 'marketplace_ad_attributions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('marketplace_ad_campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='RESTRICT'), nullable=False, index=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='SET NULL'), nullable=True)
    attributed_revenue: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    attribution_model: Mapped[str] = mapped_column(String(40), nullable=False, default='last_touch')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('campaign_id', 'order_id', name='uq_ad_attribution_order'), CheckConstraint('attributed_revenue >= 0', name='ck_ad_attribution_revenue'))

class MarketplaceCustomerCaseMessage(Base):
    __tablename__ = 'marketplace_customer_case_messages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey('marketplace_customer_cases.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    sender_role: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class MarketplaceSellerHealthSnapshot(Base):
    __tablename__ = 'marketplace_seller_health_snapshots'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispute_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    return_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    defect_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    cancellation_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    dispute_rate: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='healthy')
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('seller_tenant_id', 'period_start', 'period_end', name='uq_health_snapshot_period'),)

class MarketplaceFeedJob(Base):
    __tablename__ = 'marketplace_feed_jobs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    feed_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='queued')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (CheckConstraint('attempts >= 0', name='ck_feed_attempts'),)

class MarketplaceWebhookDelivery(Base):
    __tablename__ = 'marketplace_webhook_deliveries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_app_id: Mapped[int] = mapped_column(ForeignKey('marketplace_integration_apps.id', ondelete='CASCADE'), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='queued')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint('integration_app_id', 'event_type', 'event_id', name='uq_webhook_delivery_event'),)

class MarketplaceAnalyticsSnapshot(Base):
    __tablename__ = 'marketplace_analytics_snapshots'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    dimensions_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (Index('ix_analytics_snapshot_lookup', 'tenant_id', 'metric_code', 'period_end'),)
