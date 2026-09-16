from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class MarketplacePricingRule(Base):
    __tablename__='marketplace_pricing_rules'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(160),nullable=False)
    scope_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    action_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    min_price: Mapped[Decimal|None]=mapped_column(Numeric(20,4),nullable=True)
    max_price: Mapped[Decimal|None]=mapped_column(Numeric(20,4),nullable=True)
    active: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    priority: Mapped[int]=mapped_column(Integer,nullable=False,default=100)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(CheckConstraint('priority >= 0',name='ck_pricing_rule_priority'),)

class MarketplacePromotion(Base):
    __tablename__='marketplace_promotions'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    code: Mapped[str|None]=mapped_column(String(80),nullable=True)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    kind: Mapped[str]=mapped_column(String(40),nullable=False)
    config_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    starts_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    ends_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='draft')
    budget: Mapped[Decimal|None]=mapped_column(Numeric(20,4),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(UniqueConstraint('seller_tenant_id','code',name='uq_promotion_seller_code'),CheckConstraint("status IN ('draft','scheduled','active','paused','ended','cancelled')",name='ck_promotion_status'),Index('ix_promotion_window','starts_at','ends_at'))

class MarketplacePromotionItem(Base):
    __tablename__='marketplace_promotion_items'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    promotion_id: Mapped[int]=mapped_column(ForeignKey('marketplace_promotions.id',ondelete='CASCADE'),nullable=False,index=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='CASCADE'),nullable=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(UniqueConstraint('promotion_id','listing_id',name='uq_promotion_listing'),)

class MarketplaceBrand(Base):
    __tablename__='marketplace_brands'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    slug: Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='pending')
    registry_ref: Mapped[str|None]=mapped_column(String(255),nullable=True)
    metadata_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(CheckConstraint("status IN ('pending','verified','suspended','closed')",name='ck_brand_status'),)

class MarketplaceBrandStore(Base):
    __tablename__='marketplace_brand_stores'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    brand_id: Mapped[int]=mapped_column(ForeignKey('marketplace_brands.id',ondelete='CASCADE'),nullable=False,index=True)
    slug: Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    title: Mapped[str]=mapped_column(String(200),nullable=False)
    content_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='draft')
    published_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceAdCampaign(Base):
    __tablename__='marketplace_ad_campaigns'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    brand_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_brands.id',ondelete='SET NULL'),nullable=True,index=True)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    kind: Mapped[str]=mapped_column(String(40),nullable=False)
    objective: Mapped[str]=mapped_column(String(60),nullable=False,default='sales')
    budget_daily: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=0)
    bid_strategy: Mapped[str]=mapped_column(String(40),nullable=False,default='manual')
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='draft')
    starts_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    ends_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(CheckConstraint('budget_daily >= 0',name='ck_ad_budget_nonnegative'),)

class MarketplaceAdGroup(Base):
    __tablename__='marketplace_ad_groups'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    campaign_id: Mapped[int]=mapped_column(ForeignKey('marketplace_ad_campaigns.id',ondelete='CASCADE'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    default_bid: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=0)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='active')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceAdTarget(Base):
    __tablename__='marketplace_ad_targets'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    ad_group_id: Mapped[int]=mapped_column(ForeignKey('marketplace_ad_groups.id',ondelete='CASCADE'),nullable=False,index=True)
    target_type: Mapped[str]=mapped_column(String(40),nullable=False)
    target_value: Mapped[str]=mapped_column(String(255),nullable=False)
    bid: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=0)
    negative: Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    active: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    __table_args__=(UniqueConstraint('ad_group_id','target_type','target_value',name='uq_ad_target'),)

class MarketplaceB2BPrice(Base):
    __tablename__='marketplace_b2b_prices'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='CASCADE'),nullable=False,index=True)
    currency: Mapped[str]=mapped_column(String(10),nullable=False)
    unit_price: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    min_quantity: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False,default=1)
    active: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    __table_args__=(UniqueConstraint('seller_tenant_id','listing_id','currency','min_quantity',name='uq_b2b_price_tier'),CheckConstraint('unit_price >= 0 AND min_quantity > 0',name='ck_b2b_price_positive'))

class MarketplaceBundle(Base):
    __tablename__='marketplace_bundles'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    sku: Mapped[str]=mapped_column(String(120),nullable=False)
    price: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    currency: Mapped[str]=mapped_column(String(10),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='draft')
    components_json: Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(UniqueConstraint('seller_tenant_id','sku',name='uq_bundle_seller_sku'),CheckConstraint('price >= 0',name='ck_bundle_price_nonnegative'))

class MarketplaceSubscriptionOffer(Base):
    __tablename__='marketplace_subscription_offers'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    listing_id: Mapped[int]=mapped_column(ForeignKey('marketplace_listings.id',ondelete='CASCADE'),nullable=False,index=True)
    interval_unit: Mapped[str]=mapped_column(String(20),nullable=False)
    interval_count: Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    discount_bps: Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    active: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    __table_args__=(UniqueConstraint('seller_tenant_id','listing_id','interval_unit','interval_count',name='uq_subscription_offer'),CheckConstraint('interval_count > 0 AND discount_bps BETWEEN 0 AND 10000',name='ck_subscription_terms'))

class MarketplaceCustomerCase(Base):
    __tablename__='marketplace_customer_cases'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    buyer_user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False,index=True)
    seller_tenant_id: Mapped[int|None]=mapped_column(ForeignKey('tenants.id',ondelete='SET NULL'),nullable=True,index=True)
    order_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_orders.id',ondelete='SET NULL'),nullable=True,index=True)
    case_type: Mapped[str]=mapped_column(String(60),nullable=False)
    subject: Mapped[str]=mapped_column(String(255),nullable=False)
    description: Mapped[str]=mapped_column(Text,nullable=False,default='')
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='open')
    priority: Mapped[str]=mapped_column(String(20),nullable=False,default='normal')
    resolution_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class MarketplaceSellerHealthMetric(Base):
    __tablename__='marketplace_seller_health_metrics'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    metric_code: Mapped[str]=mapped_column(String(80),nullable=False)
    value: Mapped[Decimal]=mapped_column(Numeric(20,6),nullable=False)
    target: Mapped[Decimal|None]=mapped_column(Numeric(20,6),nullable=True)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='healthy')
    period_start: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    period_end: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    details_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    __table_args__=(Index('ix_seller_health_metric_period','seller_tenant_id','metric_code','period_end'),)

class MarketplaceWarehouse(Base):
    __tablename__='marketplace_warehouses'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    code: Mapped[str]=mapped_column(String(80),nullable=False)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    warehouse_type: Mapped[str]=mapped_column(String(40),nullable=False,default='seller')
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='active')
    location_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    __table_args__=(UniqueConstraint('owner_tenant_id','code',name='uq_warehouse_owner_code'),)

class MarketplaceInventoryTransfer(Base):
    __tablename__='marketplace_inventory_transfers'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    seller_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    from_warehouse_id: Mapped[int]=mapped_column(ForeignKey('marketplace_warehouses.id',ondelete='RESTRICT'),nullable=False)
    to_warehouse_id: Mapped[int]=mapped_column(ForeignKey('marketplace_warehouses.id',ondelete='RESTRICT'),nullable=False)
    sku_id: Mapped[int|None]=mapped_column(ForeignKey('marketplace_skus.id',ondelete='SET NULL'),nullable=True)
    quantity: Mapped[Decimal]=mapped_column(Numeric(20,4),nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='draft')
    reference: Mapped[str]=mapped_column(String(120),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(UniqueConstraint('seller_tenant_id','reference',name='uq_inventory_transfer_reference'),CheckConstraint('quantity > 0',name='ck_inventory_transfer_qty'))

class MarketplacePickupPoint(Base):
    __tablename__='marketplace_pickup_points'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    operator_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    code: Mapped[str]=mapped_column(String(80),nullable=False)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    address_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='active')
    __table_args__=(UniqueConstraint('operator_tenant_id','code',name='uq_pickup_operator_code'),)

class MarketplaceServiceArea(Base):
    __tablename__='marketplace_service_areas'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    operator_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    code: Mapped[str]=mapped_column(String(80),nullable=False)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    rules_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    active: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    __table_args__=(UniqueConstraint('operator_tenant_id','code',name='uq_service_area_operator_code'),)

class MarketplaceReportJob(Base):
    __tablename__='marketplace_report_jobs'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    report_type: Mapped[str]=mapped_column(String(80),nullable=False)
    parameters_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='queued')
    result_uri: Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceNotification(Base):
    __tablename__='marketplace_notifications'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    recipient_user_id: Mapped[str|None]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=True,index=True)
    notification_type: Mapped[str]=mapped_column(String(80),nullable=False)
    title: Mapped[str]=mapped_column(String(255),nullable=False)
    body: Mapped[str]=mapped_column(Text,nullable=False,default='')
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    channel: Mapped[str]=mapped_column(String(30),nullable=False,default='in_app')
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='queued')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketplaceIntegrationApp(Base):
    __tablename__='marketplace_integration_apps'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    owner_tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    name: Mapped[str]=mapped_column(String(200),nullable=False)
    client_id: Mapped[str]=mapped_column(String(160),nullable=False,unique=True)
    scopes_json: Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    status: Mapped[str]=mapped_column(String(30),nullable=False,default='active')
    webhook_url: Mapped[str|None]=mapped_column(String(500),nullable=True)
    rate_limit_per_minute: Mapped[int]=mapped_column(Integer,nullable=False,default=60)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
