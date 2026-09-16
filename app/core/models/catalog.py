from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class MarketplaceCatalogGroup(Base):
    __tablename__ = 'marketplace_catalog_groups'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('active','hidden','archived')", name='ck_market_catalog_group_status'),)


class MarketplaceProduct(Base):
    __tablename__ = 'marketplace_products'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_categories.id', ondelete='SET NULL'), nullable=True, index=True)
    catalog_group_id: Mapped[int | None] = mapped_column(ForeignKey('marketplace_catalog_groups.id', ondelete='SET NULL'), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    brand: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('seller_tenant_id', 'market_id', 'slug', name='uq_market_product_seller_market_slug'),
        CheckConstraint("status IN ('draft','active','archived')", name='ck_market_product_status'),
        Index('ix_market_product_public', 'status', 'category_id', 'seller_tenant_id'),
    )


class MarketplaceSKU(Base):
    __tablename__ = 'marketplace_skus'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('marketplace_products.id', ondelete='CASCADE'), nullable=False, index=True)
    sku_code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    item_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('product_id', 'sku_code', name='uq_market_sku_product_code'),
        CheckConstraint("sku_code <> ''", name='ck_market_sku_code_nonempty'),
    )


class MarketplaceOffer(Base):
    __tablename__ = 'marketplace_offers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int | None] = mapped_column(ForeignKey('market_contexts.id', ondelete='CASCADE'), nullable=True, index=True)
    seller_tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey('marketplace_skus.id', ondelete='RESTRICT'), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False)
    stock_policy: Mapped[str] = mapped_column(String(20), nullable=False, default='managed')
    warehouse_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_fee: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('seller_tenant_id', 'market_id', 'sku_id', name='uq_market_offer_seller_market_sku'),
        CheckConstraint('unit_price >= 0', name='ck_market_offer_price_nonnegative'),
        CheckConstraint('shipping_fee >= 0', name='ck_market_offer_shipping_nonnegative'),
        CheckConstraint('delivery_days IS NULL OR delivery_days >= 0', name='ck_market_offer_delivery_days_nonnegative'),
        CheckConstraint("stock_policy IN ('managed','unmanaged')", name='ck_market_offer_stock_policy'),
        CheckConstraint("status IN ('draft','active','paused','archived')", name='ck_market_offer_status'),
        Index('ix_market_offer_seller_status', 'seller_tenant_id', 'status'),
    )
