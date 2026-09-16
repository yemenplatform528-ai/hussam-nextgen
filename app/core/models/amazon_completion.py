from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class MarketplacePromotionRule(Base):
    __tablename__='marketplace_promotion_rules'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    promotion_id: Mapped[int]=mapped_column(ForeignKey('marketplace_promotions.id',ondelete='CASCADE'),nullable=False,index=True)
    stack_group: Mapped[str]=mapped_column(String(80),nullable=False,default='default')
    priority: Mapped[int]=mapped_column(Integer,nullable=False,default=100)
    stackable: Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    exclusion_codes_json: Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    max_discount: Mapped[Decimal|None]=mapped_column(Numeric(20,4),nullable=True)

class MarketplaceCouponBudget(Base):
    __tablename__='marketplace_coupon_budgets'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    coupon_id: Mapped[int]=mapped_column(ForeignKey('marketplace_coupons.id',ondelete='CASCADE'),nullable=False,unique=True)
    budget_amount: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    consumed_amount: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=0)
    currency: Mapped[str]=mapped_column(String(10),nullable=False)
    __table_args__=(CheckConstraint('budget_amount >= 0 AND consumed_amount >= 0 AND consumed_amount <= budget_amount',name='ck_coupon_budget_bounds'),)

class MarketplacePriceCompetitor(Base):
    __tablename__='marketplace_price_competitors'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='CASCADE'),nullable=False,index=True)
    source: Mapped[str]=mapped_column(String(80),nullable=False)
    price: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    currency: Mapped[str]=mapped_column(String(10),nullable=False)
    observed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(Index('ix_price_competitor_listing_time','listing_id','observed_at'),)

class MarketplaceSellerEnforcement(Base):
    __tablename__='marketplace_seller_enforcements'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    reason_code: Mapped[str]=mapped_column(String(80),nullable=False)
    severity: Mapped[str]=mapped_column(String(30),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='active')
    action: Mapped[str]=mapped_column(String(50),nullable=False)
    evidence_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    starts_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    ends_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceSellerAppeal(Base):
    __tablename__='marketplace_seller_appeals'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    enforcement_id: Mapped[int]=mapped_column(ForeignKey('marketplace_seller_enforcements.id',ondelete='CASCADE'),nullable=False,index=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    reason: Mapped[str]=mapped_column(Text,nullable=False)
    evidence_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='submitted')
    resolution_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    resolved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceCaseSLA(Base):
    __tablename__='marketplace_case_slas'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    case_id: Mapped[int]=mapped_column(ForeignKey('marketplace_customer_cases.id',ondelete='CASCADE'),nullable=False,unique=True)
    due_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='open')
    assigned_to: Mapped[str|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    escalation_level: Mapped[int]=mapped_column(Integer,nullable=False,default=0)

class MarketplaceCaseEvent(Base):
    __tablename__='marketplace_case_events'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    case_id: Mapped[int]=mapped_column(ForeignKey('marketplace_customer_cases.id',ondelete='CASCADE'),nullable=False,index=True)
    event_type: Mapped[str]=mapped_column(String(60),nullable=False)
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceShipment(Base):
    __tablename__='marketplace_shipments'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    order_id: Mapped[int]=mapped_column(ForeignKey('marketplace_orders.id',ondelete='RESTRICT'),nullable=False,index=True)
    carrier_code: Mapped[str]=mapped_column(String(80),nullable=False)
    tracking_number: Mapped[str]=mapped_column(String(160),nullable=False)
    service_level: Mapped[str]=mapped_column(String(80),nullable=False,default='standard')
    promised_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status: Mapped[str]=mapped_column(String(40),nullable=False,default='label_created')
    pod_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(UniqueConstraint('carrier_code','tracking_number',name='uq_shipment_carrier_tracking'),)

class MarketplaceShipmentEvent(Base):
    __tablename__='marketplace_shipment_events'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    shipment_id: Mapped[int]=mapped_column(ForeignKey('marketplace_shipments.id',ondelete='CASCADE'),nullable=False,index=True)
    event_code: Mapped[str]=mapped_column(String(60),nullable=False)
    event_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    location_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    raw_payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    __table_args__=(UniqueConstraint('shipment_id','event_code','event_at',name='uq_shipment_event'),)

class MarketplaceDeliveryPromise(Base):
    __tablename__='marketplace_delivery_promises'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='CASCADE'),nullable=False,index=True)
    service_area_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_service_areas.id',ondelete='SET NULL'),nullable=True)
    promised_from: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    promised_to: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    capacity_units: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=0)

class MarketplaceAdPacing(Base):
    __tablename__='marketplace_ad_pacing'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    campaign_id: Mapped[int]=mapped_column(ForeignKey('marketplace_ad_campaigns.id',ondelete='CASCADE'),nullable=False,unique=True)
    day_key: Mapped[str]=mapped_column(String(20),nullable=False)
    spend: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=0)
    impressions: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    clicks: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    conversions: Mapped[int]=mapped_column(Integer,nullable=False,default=0)

class MarketplaceReportRun(Base):
    __tablename__='marketplace_report_runs'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    report_job_id: Mapped[int]=mapped_column(ForeignKey('marketplace_report_jobs.id',ondelete='CASCADE'),nullable=False,index=True)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='queued')
    attempt: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    output_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    error: Mapped[str|None]=mapped_column(Text,nullable=True)
    started_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceNotificationDelivery(Base):
    __tablename__='marketplace_notification_deliveries'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    notification_id: Mapped[int]=mapped_column(ForeignKey('marketplace_notifications.id',ondelete='CASCADE'),nullable=False,index=True)
    channel: Mapped[str]=mapped_column(String(30),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='queued')
    attempts: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    last_error: Mapped[str|None]=mapped_column(Text,nullable=True)
    next_attempt_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceIntegrationCredential(Base):
    __tablename__='marketplace_integration_credentials'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    integration_app_id: Mapped[int]=mapped_column(ForeignKey('marketplace_integration_apps.id',ondelete='CASCADE'),nullable=False,index=True)
    subject_user_id: Mapped[str|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True)
    scopes_json: Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    token_hash: Mapped[str]=mapped_column(String(255),nullable=False,unique=True)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    revoked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceRateLimitBucket(Base):
    __tablename__='marketplace_rate_limit_buckets'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    integration_app_id: Mapped[int]=mapped_column(ForeignKey('marketplace_integration_apps.id',ondelete='CASCADE'),nullable=False)
    window_key: Mapped[str]=mapped_column(String(80),nullable=False)
    used: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    limit_value: Mapped[int]=mapped_column(Integer,nullable=False)
    __table_args__=(UniqueConstraint('integration_app_id','window_key',name='uq_rate_limit_bucket'),)

class MarketplaceAnalyticsEvent(Base):
    __tablename__='marketplace_analytics_events'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    event_type: Mapped[str]=mapped_column(String(80),nullable=False,index=True)
    entity_id: Mapped[str|None]=mapped_column(String(160),nullable=True)
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False,index=True)
    value: Mapped[Decimal]=mapped_column(Numeric(24,6),nullable=False,default=0)
    dimensions_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class MarketplaceB2BPackageTier(Base):
    __tablename__='marketplace_b2b_package_tiers'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='CASCADE'),nullable=False,index=True)
    package_qty: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    unit_label: Mapped[str]=mapped_column(String(40),nullable=False,default='unit')
    __table_args__=(UniqueConstraint('seller_tenant_id','listing_id','package_qty',name='uq_b2b_package_tier'),)

class MarketplaceB2BQuote(Base):
    __tablename__='marketplace_b2b_quotes'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    buyer_user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='RESTRICT'),nullable=False)
    quantity: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    quoted_unit_price: Mapped[Decimal|None]=mapped_column(Numeric(20,4),nullable=True)
    currency: Mapped[str]=mapped_column(String(10),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='requested')
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceTaxExemption(Base):
    __tablename__='marketplace_tax_exemptions'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    buyer_user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True)
    certificate_ref: Mapped[str]=mapped_column(String(200),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='pending')
    jurisdiction: Mapped[str]=mapped_column(String(120),nullable=False)
    valid_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceBundleReservation(Base):
    __tablename__='marketplace_bundle_reservations'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    bundle_id: Mapped[int]=mapped_column(ForeignKey('marketplace_bundles.id',ondelete='CASCADE'),nullable=False,index=True)
    order_id: Mapped[int]=mapped_column(ForeignKey('marketplace_orders.id',ondelete='RESTRICT'),nullable=False,index=True)
    quantity: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    component_snapshot_json: Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='reserved')
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceSubscriptionInstance(Base):
    __tablename__='marketplace_subscription_instances'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    offer_id: Mapped[int]=mapped_column(ForeignKey('marketplace_subscription_offers.id',ondelete='RESTRICT'),nullable=False,index=True)
    buyer_user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True)
    next_run_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='active')
    cycle_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    last_order_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_orders.id',ondelete='SET NULL'),nullable=True)

class MarketplaceBrandContentReview(Base):
    __tablename__='marketplace_brand_content_reviews'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    brand_store_id: Mapped[int]=mapped_column(ForeignKey('marketplace_brand_stores.id',ondelete='CASCADE'),nullable=False,index=True)
    reviewer_tenant_id: Mapped[int|None]=mapped_column(ForeignKey('tenants.id',ondelete='SET NULL'),nullable=True)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='pending')
    reason: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceBrandProtectionCase(Base):
    __tablename__='marketplace_brand_protection_cases'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    brand_id: Mapped[int]=mapped_column(ForeignKey('marketplace_brands.id',ondelete='CASCADE'),nullable=False,index=True)
    listing_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='SET NULL'),nullable=True)
    case_type: Mapped[str]=mapped_column(String(60),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='open')
    evidence_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    resolution_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class MarketplaceBulkIssue(Base):
    __tablename__='marketplace_bulk_issues'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    feed_job_id: Mapped[int]=mapped_column(ForeignKey('marketplace_feed_jobs.id',ondelete='CASCADE'),nullable=False,index=True)
    row_number: Mapped[int]=mapped_column(Integer,nullable=False)
    field_name: Mapped[str]=mapped_column(String(120),nullable=False)
    code: Mapped[str]=mapped_column(String(80),nullable=False)
    message: Mapped[str]=mapped_column(Text,nullable=False)
    severity: Mapped[str]=mapped_column(String(20),nullable=False,default='error')

class MarketplaceSearchEvent(Base):
    __tablename__='marketplace_search_events'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    buyer_user_id: Mapped[str|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'),nullable=True,index=True)
    query: Mapped[str]=mapped_column(String(500),nullable=False)
    result_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    clicked_listing_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='SET NULL'),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class HUSExecutionRecord(Base):
    __tablename__='hus_execution_records'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    compilation_id: Mapped[str]=mapped_column(ForeignKey('hus_compilations.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_id: Mapped[str]=mapped_column(String(255),nullable=False)
    action: Mapped[str]=mapped_column(String(160),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='approved')
    input_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    output_json: Mapped[dict|None]=mapped_column(JSON,nullable=True)
    approval_ref: Mapped[str|None]=mapped_column(String(160),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
