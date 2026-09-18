from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint, Index, text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc(): return datetime.now(timezone.utc)

class MarketplaceSellerProfile(Base):
    __tablename__ = 'marketplace_seller_profiles'
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    seller_type: Mapped[str] = mapped_column(String(30), nullable=False, default='business')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("seller_type IN ('business','individual','institution')", name='ck_market_seller_type'),
        CheckConstraint("status IN ('pending','active','suspended','closed')", name='ck_market_seller_status'),
    )

class MarketplaceCategory(Base):
    __tablename__ = 'marketplace_categories'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_categories.id', ondelete='SET NULL'), nullable=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

class MarketplaceListing(Base):
    __tablename__ = 'marketplace_listings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_products.id', ondelete='SET NULL'), nullable=True, index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_skus.id', ondelete='SET NULL'), nullable=True, index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_offers.id', ondelete='SET NULL'), nullable=True, unique=True, index=True)
    item_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    warehouse_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_categories.id', ondelete='SET NULL'), nullable=True)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    listing_type: Mapped[str] = mapped_column(String(20), nullable=False, default='product')
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='draft')
    stock_policy: Mapped[str] = mapped_column(String(20), nullable=False, default='managed')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    __table_args__ = (
        UniqueConstraint('seller_tenant_id','market_id','slug', name='uq_market_listing_seller_market_slug'),
        CheckConstraint("listing_type IN ('product','service')", name='ck_market_listing_type'),
        CheckConstraint("status IN ('draft','published','paused','archived')", name='ck_market_listing_status'),
        CheckConstraint("moderation_status IN ('pending','approved','rejected','suspended')", name='ck_market_listing_moderation_status'),
        CheckConstraint("stock_policy IN ('managed','unmanaged')", name='ck_market_listing_stock_policy'),
        CheckConstraint('unit_price >= 0', name='ck_market_listing_price_nonnegative'),
        CheckConstraint("(listing_type = 'product' AND item_id IS NOT NULL AND warehouse_id IS NOT NULL) OR listing_type = 'service'", name='ck_market_listing_product_refs'),
        Index('ix_market_listing_public','status','category_id','seller_tenant_id'),
        Index('ix_market_listing_moderation','moderation_status','status'),
    )

class MarketplaceBuyerProfile(Base):
    __tablename__ = 'marketplace_buyer_profiles'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class MarketplaceAddress(Base):
    __tablename__ = 'marketplace_addresses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    governorate: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    address_line: Mapped[str] = mapped_column(String(500), nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(300), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='SET NULL'), nullable=True, index=True)
    governorate_id: Mapped[int | None] = mapped_column(ForeignKey('market_geographies.id', ondelete='SET NULL'), nullable=True, index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey('market_geographies.id', ondelete='SET NULL'), nullable=True, index=True)
    locality_id: Mapped[int | None] = mapped_column(ForeignKey('market_geographies.id', ondelete='SET NULL'), nullable=True, index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(200), nullable=True)
    street: Mapped[str | None] = mapped_column(String(200), nullable=True)
    building: Mapped[str | None] = mapped_column(String(120), nullable=True)
    geo_lat: Mapped[object | None] = mapped_column(Numeric(10, 7), nullable=True)
    geo_lng: Mapped[object | None] = mapped_column(Numeric(10, 7), nullable=True)
    address_confidence: Mapped[str] = mapped_column(String(10), nullable=False, default='low')
    delivery_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        CheckConstraint("country_code IS NULL OR length(country_code) = 2", name='ck_market_address_country_code'),
        CheckConstraint("address_confidence IN ('high','medium','low')", name='ck_market_address_confidence'),
        CheckConstraint("geo_lat IS NULL OR (geo_lat >= -90 AND geo_lat <= 90)", name='ck_market_address_lat'),
        CheckConstraint("geo_lng IS NULL OR (geo_lng >= -180 AND geo_lng <= 180)", name='ck_market_address_lng'),
        ForeignKeyConstraint(['market_id', 'governorate_id'], ['market_geographies.market_id', 'market_geographies.id'], name='fk_marketplace_address_governorate_market', ondelete='SET NULL'),
        ForeignKeyConstraint(['market_id', 'district_id'], ['market_geographies.market_id', 'market_geographies.id'], name='fk_marketplace_address_district_market', ondelete='SET NULL'),
        ForeignKeyConstraint(['market_id', 'locality_id'], ['market_geographies.market_id', 'market_geographies.id'], name='fk_marketplace_address_locality_market', ondelete='SET NULL'),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)

class MarketplaceCart(Base):
    __tablename__ = 'marketplace_carts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('buyer_user_id','market_id',name='uq_market_cart_buyer_market'), CheckConstraint("status IN ('active','checked_out','abandoned')", name='ck_market_cart_status'),)

class MarketplaceCartItem(Base):
    __tablename__ = 'marketplace_cart_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey('marketplace_carts.id', ondelete='CASCADE'), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='RESTRICT'), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('cart_id','listing_id', name='uq_market_cart_listing'), CheckConstraint('quantity > 0', name='ck_market_cart_quantity_positive'))

class MarketplaceCustomerOrder(Base):
    __tablename__ = 'marketplace_customer_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    subtotal: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    shipping_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending_payment')
    shipping_address_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_addresses.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('pending_payment','paid','processing','partially_shipped','shipped','delivered','completed','cancelled','refunded','disputed')", name='ck_market_customer_order_status'),
        CheckConstraint('subtotal >= 0 AND shipping_fee >= 0 AND total >= 0', name='ck_market_customer_order_amounts'),
    )


class MarketplaceOrder(Base):
    __tablename__ = 'marketplace_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    customer_order_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_customer_orders.id', ondelete='SET NULL'), nullable=True, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey('sales_orders.id', ondelete='SET NULL'), nullable=True, unique=True)
    shipping_address_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_addresses.id', ondelete='SET NULL'), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    subtotal: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    shipping_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    platform_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending_payment')
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('pending_payment','paid','processing','shipped','delivered','completed','cancelled','partially_refunded','refunded','disputed')", name='ck_market_order_status'),
        CheckConstraint('subtotal >= 0 AND shipping_fee >= 0 AND platform_fee >= 0 AND total >= 0', name='ck_market_order_amounts_nonnegative'),
    )

class MarketplaceSellerOrder(Base):
    __tablename__ = 'marketplace_seller_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_customer_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='CASCADE'), nullable=False, unique=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending_payment')
    subtotal: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    shipping_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('customer_order_id','seller_tenant_id', name='uq_market_seller_order_customer_seller'),
        CheckConstraint("status IN ('pending_payment','paid','processing','ready_for_fulfillment','fulfilled','cancelled','returned','refunded','disputed')", name='ck_market_seller_order_status'),
        CheckConstraint('subtotal >= 0 AND shipping_fee >= 0 AND total >= 0', name='ck_market_seller_order_amounts'),
    )


class MarketplaceFulfillment(Base):
    __tablename__ = 'marketplace_fulfillments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_seller_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(30), nullable=False, default='seller_fulfilled')
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    shipment_id: Mapped[int | None] = mapped_column(ForeignKey('shipments.id', ondelete='SET NULL'), nullable=True, unique=True)
    carrier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("method IN ('seller_fulfilled','hussam_delivery','external_carrier','pickup')", name='ck_market_fulfillment_method'),
        CheckConstraint("status IN ('pending','assigned','ready','picked_up','in_transit','out_for_delivery','delivered','failed','returned','cancelled')", name='ck_market_fulfillment_status'),
    )


class MarketplaceOrderLine(Base):
    __tablename__ = 'marketplace_order_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='RESTRICT'), nullable=False)
    sales_order_line_id: Mapped[int | None] = mapped_column(ForeignKey('sales_order_lines.id', ondelete='SET NULL'), nullable=True)
    title_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    line_total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0 AND unit_price >= 0 AND line_total >= 0', name='ck_market_order_line_amounts'),)




class MarketplaceFeeRule(Base):
    __tablename__ = 'marketplace_fee_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default='global')
    seller_tenant_id: Mapped[int | None] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_categories.id', ondelete='CASCADE'), nullable=True, index=True)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    fixed_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False, default='v1')
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("scope IN ('global','seller','category')", name='ck_market_fee_rule_scope'),
        CheckConstraint('commission_bps >= 0 AND commission_bps <= 3000', name='ck_market_fee_rule_bps'),
        CheckConstraint('fixed_fee >= 0', name='ck_market_fee_rule_fixed_nonnegative'),
        CheckConstraint("(scope = 'global' AND seller_tenant_id IS NULL AND category_id IS NULL) OR (scope = 'seller' AND seller_tenant_id IS NOT NULL AND category_id IS NULL) OR (scope = 'category' AND category_id IS NOT NULL AND seller_tenant_id IS NULL)", name='ck_market_fee_rule_scope_refs'),
        CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name='ck_market_fee_rule_effective_window'),
    )

class MarketplaceChargeRule(Base):
    __tablename__ = 'marketplace_charge_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    charge_type: Mapped[str] = mapped_column(String(40), nullable=False)
    jurisdiction_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fixed_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False, default='v1')
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("charge_type IN ('tax','regulatory_fee','levy')", name='ck_market_charge_rule_type'),
        CheckConstraint('rate_bps >= 0 AND rate_bps <= 10000', name='ck_market_charge_rule_bps'),
        CheckConstraint('fixed_amount >= 0', name='ck_market_charge_rule_fixed_nonnegative'),
        CheckConstraint('effective_to IS NULL OR effective_to > effective_from', name='ck_market_charge_rule_effective_window'),
    )

class MarketplaceOrderCharge(Base):
    __tablename__ = 'marketplace_order_charges'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_charge_rules.id', ondelete='SET NULL'), nullable=True)
    charge_type: Mapped[str] = mapped_column(String(40), nullable=False)
    jurisdiction_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    basis_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    fixed_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("charge_type IN ('tax','regulatory_fee','levy')", name='ck_market_order_charge_type'),
        CheckConstraint('basis_amount >= 0 AND rate_bps >= 0 AND fixed_amount >= 0 AND amount >= 0', name='ck_market_order_charge_amounts'),
        UniqueConstraint('marketplace_order_id','charge_type','jurisdiction_code','policy_version', name='uq_market_order_charge_policy'),
    )

class MarketplaceOrderFee(Base):
    __tablename__ = 'marketplace_order_fees'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_fee_rules.id', ondelete='SET NULL'), nullable=True)
    fee_type: Mapped[str] = mapped_column(String(40), nullable=False, default='commission')
    basis_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    fixed_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False, default='v1')
    policy_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("fee_type IN ('commission','payment','fulfillment','adjustment')", name='ck_market_order_fee_type'),
        CheckConstraint('basis_amount >= 0 AND commission_bps >= 0 AND fixed_fee >= 0 AND amount >= 0', name='ck_market_order_fee_amounts'),
    )

class MarketplacePayoutDestination(Base):
    __tablename__ = 'marketplace_payout_destinations'
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    external_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('pending','verified','disabled')", name='ck_market_payout_destination_status'),
        UniqueConstraint('provider','external_reference', name='uq_market_payout_destination_external'),
    )

class MarketplacePayout(Base):
    __tablename__ = 'marketplace_payouts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='RESTRICT'), nullable=False, unique=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    gross_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    platform_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    net_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='held')
    eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    settlement_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    payout_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    payout_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (CheckConstraint("status IN ('held','eligible','processing','paid','reversed')", name='ck_market_payout_status'), CheckConstraint('gross_amount >= platform_fee AND net_amount = gross_amount - platform_fee', name='ck_market_payout_math'))

class MarketplaceSellerBalanceEntry(Base):
    __tablename__ = 'marketplace_seller_balance_entries'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    marketplace_payout_id: Mapped[int] = mapped_column(ForeignKey('marketplace_payouts.id', ondelete='RESTRICT'), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("entry_type IN ('credit','debit','refund_reversal','refund_recovery','payout_debit')", name='ck_market_seller_balance_entry_type'),
        CheckConstraint('amount > 0', name='ck_market_seller_balance_entry_amount_positive'),
        UniqueConstraint('marketplace_payout_id','entry_type','source_reference', name='uq_market_seller_balance_source'),
    )

class MarketplaceReview(Base):
    __tablename__ = 'marketplace_reviews'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='CASCADE'), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='RESTRICT'), nullable=False)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default='')
    body: Mapped[str] = mapped_column(Text, nullable=False, default='')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='published')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('marketplace_order_id','listing_id','buyer_user_id', name='uq_market_review_once'), CheckConstraint('rating BETWEEN 1 AND 5', name='ck_market_review_rating'), CheckConstraint("status IN ('published','hidden','removed')", name='ck_market_review_status'))

class MarketplaceDispute(Base):
    __tablename__ = 'marketplace_disputes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='RESTRICT'), nullable=False, unique=True)
    opened_by_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='open')
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (CheckConstraint("status IN ('open','investigating','resolved','rejected','cancelled')", name='ck_market_dispute_status'),)

class MarketplaceSellerVerification(Base):
    __tablename__ = 'marketplace_seller_verifications'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default='')
    __table_args__ = (UniqueConstraint('seller_tenant_id', name='uq_market_seller_verification_seller'), CheckConstraint("status IN ('pending','approved','rejected')", name='ck_market_seller_verification_status'))

class MarketplaceShippingRate(Base):
    __tablename__ = 'marketplace_shipping_rates'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    governorate: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    governorate_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    district_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    locality_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint('seller_tenant_id','market_id','governorate_id','district_id','locality_id','currency',name='uq_market_shipping_rate_market_geo'),
        CheckConstraint('fee >= 0', name='ck_market_shipping_fee_nonnegative'),
        ForeignKeyConstraint(['market_id','governorate_id'], ['market_geographies.market_id','market_geographies.id'], name='fk_market_shipping_rate_governorate_market', ondelete='SET NULL'),
        ForeignKeyConstraint(['market_id','district_id'], ['market_geographies.market_id','market_geographies.id'], name='fk_market_shipping_rate_district_market', ondelete='SET NULL'),
        ForeignKeyConstraint(['market_id','locality_id'], ['market_geographies.market_id','market_geographies.id'], name='fk_market_shipping_rate_locality_market', ondelete='SET NULL'),
    )

class MarketplaceShippingQuote(Base):
    __tablename__ = 'marketplace_shipping_quotes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    address_id: Mapped[int] = mapped_column(ForeignKey('marketplace_addresses.id', ondelete='RESTRICT'), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (CheckConstraint('fee >= 0', name='ck_market_shipping_quote_fee_nonnegative'),)

class MarketplaceFavorite(Base):
    __tablename__ = 'marketplace_favorites'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    listing_id: Mapped[int] = mapped_column(ForeignKey('marketplace_listings.id', ondelete='CASCADE'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('buyer_user_id','listing_id',name='uq_market_favorite'),)

class MarketplaceReturnRequest(Base):
    __tablename__ = 'marketplace_return_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='RESTRICT'), nullable=True, index=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='RESTRICT'), nullable=False)
    opened_by_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='requested')
    refund_amount: Mapped[object | None] = mapped_column(Numeric(20,4), nullable=True)
    refund_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    refund_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    refund_scope: Mapped[str] = mapped_column(String(20), nullable=False, default='order')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (CheckConstraint("refund_scope IN ('order','items')",name='ck_market_return_refund_scope'), CheckConstraint("status IN ('requested','approved','rejected','pickup','received','inspected','refund_approved','refunded','cancelled')",name='ck_market_return_status'))

class MarketplaceReturnLine(Base):
    __tablename__ = 'marketplace_return_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_request_id: Mapped[int] = mapped_column(ForeignKey('marketplace_return_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    order_line_id: Mapped[int] = mapped_column(ForeignKey('marketplace_order_lines.id', ondelete='RESTRICT'), nullable=False, index=True)
    quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='requested')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('return_request_id','order_line_id',name='uq_market_return_line'), CheckConstraint('quantity > 0 AND unit_price >= 0 AND amount >= 0',name='ck_market_return_line_amounts'), CheckConstraint("status IN ('requested','approved','rejected','received','refunded','cancelled')",name='ck_market_return_line_status'))

class MarketplaceRefundLine(Base):
    __tablename__ = 'marketplace_refund_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_refund_id: Mapped[int] = mapped_column(ForeignKey('payment_refunds.id', ondelete='CASCADE'), nullable=False, index=True)
    return_line_id: Mapped[int] = mapped_column(ForeignKey('marketplace_return_lines.id', ondelete='RESTRICT'), nullable=False, unique=True)
    quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint('quantity > 0 AND amount > 0',name='ck_market_refund_line_positive'),)

class MarketplacePackage(Base):
    __tablename__ = 'marketplace_packages'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fulfillment_id: Mapped[int] = mapped_column(ForeignKey('marketplace_fulfillments.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='packed')
    weight_kg: Mapped[object | None] = mapped_column(Numeric(12,3), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('seller_tenant_id','reference', name='uq_market_package_seller_reference'),
        CheckConstraint("status IN ('packed','handed_over','in_transit','delivered','returned','cancelled')", name='ck_market_package_status'),
        CheckConstraint('weight_kg IS NULL OR weight_kg > 0', name='ck_market_package_weight_positive'),
    )

class MarketplacePaymentSession(Base):
    __tablename__ = 'marketplace_payment_sessions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_customer_orders.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    buyer_user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_market_payment_session_positive_amount'),
        CheckConstraint("status IN ('pending','processing','captured','failed','cancelled','refunded')", name='ck_market_payment_session_status'),
    )

class MarketplacePaymentAllocation(Base):
    __tablename__ = 'marketplace_payment_allocations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('marketplace_payment_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_seller_orders.id', ondelete='RESTRICT'), nullable=False, unique=True)
    marketplace_order_id: Mapped[int] = mapped_column(ForeignKey('marketplace_orders.id', ondelete='RESTRICT'), nullable=False, unique=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    __table_args__ = (CheckConstraint('amount > 0', name='ck_market_payment_allocation_positive_amount'),)


class MarketplaceOfferCompetition(Base):
    __tablename__ = 'marketplace_offer_competitions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    catalog_group_id: Mapped[int] = mapped_column(ForeignKey('marketplace_catalog_groups.id', ondelete='CASCADE'), nullable=False)
    featured_offer_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_offers.id', ondelete='SET NULL'), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False, default='deterministic_score')
    __table_args__ = (UniqueConstraint('market_id','catalog_group_id', name='uq_market_competition_market_group'),)

class MarketplaceOfferCompetitionScore(Base):
    __tablename__ = 'marketplace_offer_competition_scores'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey('marketplace_offer_competitions.id', ondelete='CASCADE'), nullable=False, index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey('marketplace_offers.id', ondelete='CASCADE'), nullable=False)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    shipping_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    stock: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_rating_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[object] = mapped_column(Numeric(20,8), nullable=False)
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint('competition_id','offer_id', name='uq_market_competition_offer'),
        CheckConstraint('unit_price >= 0 AND shipping_fee >= 0 AND stock >= 0', name='ck_market_competition_values'),
        CheckConstraint('score >= 0', name='ck_market_competition_score_nonnegative'),
        CheckConstraint('rank >= 1', name='ck_market_competition_rank_positive'),
    )
