import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models.core import Tenant
from app.core.models.market import MarketContext, MarketCurrency
from app.core.models.inventory import InventoryItem, Warehouse
from app.core.models.marketplace import MarketplaceCategory, MarketplaceListing, MarketplaceSellerProfile, MarketplaceSellerVerification
from app.core.models.catalog import MarketplaceProduct, MarketplaceSKU, MarketplaceOffer, MarketplaceCatalogGroup
from app.core.models.governance import OutboxEvent
from uuid import uuid4


class CatalogError(ValueError):
    pass


def money(v):
    return Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def now_utc():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ProductInput:
    slug: str
    name: str
    description: str = ''
    brand: str | None = None
    category_id: int | None = None
    market_id: int | None = None


@dataclass(frozen=True)
class SKUInput:
    sku_code: str
    name: str
    attributes: dict | None = None
    item_id: str | None = None


@dataclass(frozen=True)
class OfferInput:
    currency: str
    unit_price: Decimal
    stock_policy: str = 'managed'
    warehouse_id: str | None = None
    shipping_fee: Decimal = Decimal('0')
    delivery_days: int | None = None
    market_id: int | None = None


class CatalogService:
    """Seller-owned catalog authority: Product -> SKU -> Offer. Listing is its market presentation."""
    def __init__(self, db: Session):
        self.db = db

    def _event(self, tenant_id, typ, aggregate_type, aggregate_id, payload):
        self.db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=typ,
                                aggregate_type=aggregate_type, aggregate_id=str(aggregate_id),
                                payload=payload, published=False))


    def _market_id(self, requested=None):
        if requested is not None:
            market = self.db.scalar(select(MarketContext).where(MarketContext.id == requested, MarketContext.status != 'retired'))
            if not market:
                raise CatalogError('market not found or retired')
            return market.id
        active = self.db.scalars(select(MarketContext).where(MarketContext.status == 'active').order_by(MarketContext.id)).all()
        if len(active) == 1:
            return active[0].id
        raise CatalogError('market context is required when multiple or no active markets exist')

    def _seller(self, tenant_id):
        q = select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id == tenant_id)
        q = q.join(MarketplaceSellerVerification,
                   MarketplaceSellerVerification.seller_tenant_id == MarketplaceSellerProfile.tenant_id)
        q = q.where(MarketplaceSellerProfile.status == 'active', MarketplaceSellerVerification.status == 'approved')
        x = self.db.scalar(q)
        if not x:
            raise CatalogError('active verified marketplace seller required')
        return x

    def _category(self, category_id):
        if category_id is None:
            return None
        x = self.db.scalar(select(MarketplaceCategory).where(MarketplaceCategory.id == category_id, MarketplaceCategory.active.is_(True)))
        if not x:
            raise CatalogError('category not found')
        return x

    def create_product(self, tenant_id: int, data: ProductInput):
        self._seller(tenant_id)
        market_id = self._market_id(data.market_id)
        slug, name = (data.slug or '').strip(), (data.name or '').strip()
        if not slug or not name:
            raise CatalogError('product slug and name are required')
        category = self._category(data.category_id)
        if category is not None and category.market_id not in (None, market_id):
            raise CatalogError('category belongs to another market')
        if self.db.scalar(select(MarketplaceProduct).where(MarketplaceProduct.seller_tenant_id == tenant_id,
                                                            MarketplaceProduct.market_id == market_id,
                                                            MarketplaceProduct.slug == slug)):
            raise CatalogError('product slug already exists')
        x = MarketplaceProduct(market_id=market_id, seller_tenant_id=tenant_id, category_id=data.category_id, slug=slug,
                               name=name, description=(data.description or '').strip(),
                               brand=(data.brand or '').strip() or None, status='draft')
        self.db.add(x); self.db.flush()
        self._event(tenant_id, 'marketplace.product.created', 'product', x.id, {'slug': x.slug, 'name': x.name})
        self.db.commit(); self.db.refresh(x)
        return x

    def create_sku(self, tenant_id: int, product_id: int, data: SKUInput):
        self._seller(tenant_id)
        product = self.db.scalar(select(MarketplaceProduct).where(MarketplaceProduct.id == product_id,
                                                                    MarketplaceProduct.seller_tenant_id == tenant_id))
        if not product:
            raise CatalogError('product not found in seller tenant')
        code = (data.sku_code or '').strip()
        name = (data.name or '').strip()
        if not code or not name:
            raise CatalogError('sku code and name are required')
        if self.db.scalar(select(MarketplaceSKU).where(MarketplaceSKU.product_id == product_id,
                                                        MarketplaceSKU.sku_code == code)):
            raise CatalogError('sku code already exists for product')
        if data.item_id:
            item = self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id == tenant_id,
                                                               InventoryItem.id == data.item_id,
                                                               InventoryItem.active.is_(True)))
            if not item:
                raise CatalogError('inventory item not found in seller tenant')
        attrs = data.attributes or {}
        if not isinstance(attrs, dict):
            raise CatalogError('sku attributes must be an object')
        x = MarketplaceSKU(product_id=product_id, sku_code=code, name=name,
                           attributes_json=json.dumps(attrs, ensure_ascii=False, sort_keys=True),
                           item_id=data.item_id, active=True)
        self.db.add(x); self.db.flush()
        self._event(tenant_id, 'marketplace.sku.created', 'sku', x.id, {'product_id': product_id, 'sku_code': code})
        self.db.commit(); self.db.refresh(x)
        return x

    def create_offer(self, tenant_id: int, sku_id: int, data: OfferInput):
        self._seller(tenant_id)
        market_id = self._market_id(data.market_id)
        sku = self.db.scalar(select(MarketplaceSKU).join(MarketplaceProduct, MarketplaceProduct.id == MarketplaceSKU.product_id)
                             .where(MarketplaceSKU.id == sku_id, MarketplaceProduct.seller_tenant_id == tenant_id))
        if not sku:
            raise CatalogError('sku not found in seller tenant')
        product = self.db.get(MarketplaceProduct, sku.product_id)
        if not product or product.market_id != market_id:
            raise CatalogError('sku does not belong to the requested market')
        if data.stock_policy not in {'managed', 'unmanaged'}:
            raise CatalogError('unsupported stock policy')
        currency = (data.currency or '').strip().upper()
        if not self.db.scalar(select(MarketCurrency).where(MarketCurrency.market_id == market_id, MarketCurrency.currency == currency)):
            raise CatalogError('currency is not enabled for market')
        if not currency:
            raise CatalogError('currency is required')
        price = money(data.unit_price)
        shipping_fee = money(data.shipping_fee)
        if shipping_fee < 0: raise CatalogError('shipping fee cannot be negative')
        if data.delivery_days is not None and data.delivery_days < 0: raise CatalogError('delivery days cannot be negative')
        if price < 0:
            raise CatalogError('unit price cannot be negative')
        if data.stock_policy == 'managed':
            if not sku.item_id or not data.warehouse_id:
                raise CatalogError('managed offer requires sku inventory item and warehouse')
            wh = self.db.scalar(select(Warehouse).where(Warehouse.tenant_id == tenant_id,
                                                         Warehouse.id == data.warehouse_id,
                                                         Warehouse.active.is_(True)))
            if not wh:
                raise CatalogError('warehouse not found in seller tenant')
        elif data.warehouse_id:
            wh = self.db.scalar(select(Warehouse).where(Warehouse.tenant_id == tenant_id,
                                                         Warehouse.id == data.warehouse_id,
                                                         Warehouse.active.is_(True)))
            if not wh:
                raise CatalogError('warehouse not found in seller tenant')
        if self.db.scalar(select(MarketplaceOffer).where(MarketplaceOffer.seller_tenant_id == tenant_id,
                                                         MarketplaceOffer.market_id == market_id,
                                                         MarketplaceOffer.sku_id == sku_id)):
            raise CatalogError('seller already has an offer for this sku')
        x = MarketplaceOffer(market_id=market_id, seller_tenant_id=tenant_id, sku_id=sku_id, currency=currency,
                             unit_price=price, stock_policy=data.stock_policy,
                             warehouse_id=data.warehouse_id, shipping_fee=shipping_fee, delivery_days=data.delivery_days, status='draft')
        self.db.add(x); self.db.flush()
        self._event(tenant_id, 'marketplace.offer.created', 'offer', x.id,
                    {'sku_id': sku_id, 'currency': currency, 'unit_price': str(price)})
        self.db.commit(); self.db.refresh(x)
        return x

    def create_listing(self, tenant_id: int, offer_id: int, *, slug: str, category_id: int | None = None,
                       title: str | None = None, description: str | None = None):
        self._seller(tenant_id)
        offer = self.db.scalar(select(MarketplaceOffer).where(MarketplaceOffer.id == offer_id,
                                                               MarketplaceOffer.seller_tenant_id == tenant_id))
        if not offer:
            raise CatalogError('offer not found in seller tenant')
        if offer.market_id is None:
            raise CatalogError('offer market is required')
        sku = self.db.get(MarketplaceSKU, offer.sku_id)
        product = self.db.get(MarketplaceProduct, sku.product_id) if sku else None
        if product and product.market_id != offer.market_id:
            raise CatalogError('product and offer markets do not match')
        if not sku or not product:
            raise CatalogError('offer catalog chain is invalid')
        category = self._category(category_id if category_id is not None else product.category_id)
        if category is not None and category.market_id not in (None, offer.market_id):
            raise CatalogError('category belongs to another market')
        slug = (slug or '').strip()
        if not slug:
            raise CatalogError('listing slug is required')
        if self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.seller_tenant_id == tenant_id,
                                                            MarketplaceListing.market_id == offer.market_id,
                                                            MarketplaceListing.slug == slug)):
            raise CatalogError('listing slug already exists')
        x = MarketplaceListing(market_id=offer.market_id, seller_tenant_id=tenant_id, product_id=product.id, sku_id=sku.id,
                               offer_id=offer.id, item_id=sku.item_id, warehouse_id=offer.warehouse_id,
                               category_id=category_id if category_id is not None else product.category_id,
                               slug=slug, title=(title or product.name).strip(),
                               description=(description if description is not None else product.description) or '',
                               listing_type='product', currency=offer.currency, unit_price=offer.unit_price,
                               status='draft', stock_policy=offer.stock_policy, moderation_status='pending')
        self.db.add(x); self.db.flush()
        self._event(tenant_id, 'marketplace.listing.created', 'listing', x.id,
                    {'product_id': product.id, 'sku_id': sku.id, 'offer_id': offer.id})
        self.db.commit(); self.db.refresh(x)
        return x

    def create_product_bundle(self, tenant_id: int, *, product: ProductInput, sku: SKUInput, offer: OfferInput, listing_slug: str, listing_title: str | None = None):
        """Create Product -> SKU -> Offer -> Listing as one database transaction."""
        self._seller(tenant_id)
        market_id = self._market_id(product.market_id if product.market_id is not None else offer.market_id)
        if offer.market_id is not None and offer.market_id != market_id: raise CatalogError('product and offer markets do not match')
        slug, name = (product.slug or '').strip(), (product.name or '').strip()
        if not slug or not name: raise CatalogError('product slug and name are required')
        category = self._category(product.category_id)
        if category is not None and category.market_id not in (None, market_id): raise CatalogError('category belongs to another market')
        if self.db.scalar(select(MarketplaceProduct).where(MarketplaceProduct.seller_tenant_id==tenant_id, MarketplaceProduct.market_id==market_id, MarketplaceProduct.slug==slug)): raise CatalogError('product slug already exists')
        if not listing_slug or not listing_slug.strip(): raise CatalogError('listing slug is required')
        if self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.seller_tenant_id==tenant_id, MarketplaceListing.market_id==market_id, MarketplaceListing.slug==listing_slug.strip())): raise CatalogError('listing slug already exists')
        code, sku_name = (sku.sku_code or '').strip(), (sku.name or '').strip()
        if not code or not sku_name: raise CatalogError('sku code and name are required')
        if sku.item_id and not self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id==tenant_id, InventoryItem.id==sku.item_id, InventoryItem.active.is_(True))): raise CatalogError('inventory item not found in seller tenant')
        if offer.stock_policy not in {'managed','unmanaged'}: raise CatalogError('unsupported stock policy')
        currency=(offer.currency or '').strip().upper(); price=money(offer.unit_price); shipping_fee=money(offer.shipping_fee)
        if not currency: raise CatalogError('currency is required')
        if price < 0: raise CatalogError('unit price cannot be negative')
        if shipping_fee < 0: raise CatalogError('shipping fee cannot be negative')
        if offer.delivery_days is not None and offer.delivery_days < 0: raise CatalogError('delivery days cannot be negative')
        if offer.stock_policy=='managed' and (not sku.item_id or not offer.warehouse_id): raise CatalogError('managed offer requires sku inventory item and warehouse')
        if offer.warehouse_id and not self.db.scalar(select(Warehouse).where(Warehouse.tenant_id==tenant_id, Warehouse.id==offer.warehouse_id, Warehouse.active.is_(True))): raise CatalogError('warehouse not found in seller tenant')
        if not self.db.scalar(select(MarketCurrency).where(MarketCurrency.market_id==market_id, MarketCurrency.currency==currency)):
            raise CatalogError('currency is not enabled for market')
        p=MarketplaceProduct(market_id=market_id, seller_tenant_id=tenant_id, category_id=product.category_id, slug=slug, name=name, description=(product.description or '').strip(), brand=(product.brand or '').strip() or None, status='draft')
        self.db.add(p); self.db.flush()
        sk=MarketplaceSKU(product_id=p.id, sku_code=code, name=sku_name, attributes_json=json.dumps(sku.attributes or {}, ensure_ascii=False, sort_keys=True), item_id=sku.item_id, active=True)
        self.db.add(sk); self.db.flush()
        of=MarketplaceOffer(market_id=market_id, seller_tenant_id=tenant_id, sku_id=sk.id, currency=currency, unit_price=price, stock_policy=offer.stock_policy, warehouse_id=offer.warehouse_id, shipping_fee=shipping_fee, delivery_days=offer.delivery_days, status='draft')
        self.db.add(of); self.db.flush()
        li=MarketplaceListing(market_id=market_id, seller_tenant_id=tenant_id, product_id=p.id, sku_id=sk.id, offer_id=of.id, item_id=sk.item_id, warehouse_id=of.warehouse_id, category_id=product.category_id, slug=listing_slug.strip(), title=(listing_title or product.name).strip(), description=product.description or '', listing_type='product', currency=of.currency, unit_price=of.unit_price, status='draft', stock_policy=of.stock_policy, moderation_status='pending')
        self.db.add(li); self.db.flush()
        self._event(tenant_id,'marketplace.product.created','product',p.id,{'slug':p.slug,'name':p.name})
        self._event(tenant_id,'marketplace.sku.created','sku',sk.id,{'product_id':p.id,'sku_code':sk.sku_code})
        self._event(tenant_id,'marketplace.offer.created','offer',of.id,{'sku_id':sk.id,'currency':of.currency,'unit_price':str(of.unit_price)})
        self._event(tenant_id,'marketplace.listing.created','listing',li.id,{'product_id':p.id,'sku_id':sk.id,'offer_id':of.id})
        self.db.commit(); self.db.refresh(p); self.db.refresh(sk); self.db.refresh(of); self.db.refresh(li)
        return p, sk, of, li

    def seller_catalog(self, tenant_id: int):
        self._seller(tenant_id)
        products = self.db.scalars(select(MarketplaceProduct).where(MarketplaceProduct.seller_tenant_id == tenant_id)
                                   .order_by(MarketplaceProduct.id.desc())).all()
        result = []
        for p in products:
            skus = self.db.scalars(select(MarketplaceSKU).where(MarketplaceSKU.product_id == p.id).order_by(MarketplaceSKU.id)).all()
            sku_rows = []
            for sku in skus:
                offer = self.db.scalar(select(MarketplaceOffer).where(MarketplaceOffer.seller_tenant_id == tenant_id,
                                                                       MarketplaceOffer.sku_id == sku.id))
                listing = self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.offer_id == (offer.id if offer else -1)))
                sku_rows.append({'id': sku.id, 'sku_code': sku.sku_code, 'name': sku.name,
                                 'attributes': json.loads(sku.attributes_json or '{}'), 'item_id': sku.item_id,
                                 'offer': None if not offer else {'id': offer.id, 'currency': offer.currency,
                                     'unit_price': str(offer.unit_price), 'stock_policy': offer.stock_policy,
                                     'warehouse_id': offer.warehouse_id, 'status': offer.status},
                                 'listing': None if not listing else {'id': listing.id, 'slug': listing.slug,
                                     'status': listing.status, 'moderation_status': listing.moderation_status}})
            result.append({'id': p.id, 'slug': p.slug, 'name': p.name, 'description': p.description,
                           'brand': p.brand, 'category_id': p.category_id, 'status': p.status, 'skus': sku_rows})
        return result

    def product_view(self, product_id: int, market_id: int | None = None):
        p = self.db.get(MarketplaceProduct, product_id)
        if market_id is not None and (not p or p.market_id != market_id):
            raise CatalogError('product not found')
        if not p or p.status == 'archived':
            raise CatalogError('product not found')
        seller = self.db.get(MarketplaceSellerProfile, p.seller_tenant_id)
        if not seller or seller.status != 'active':
            raise CatalogError('product seller is not active')
        skus = self.db.scalars(select(MarketplaceSKU).where(MarketplaceSKU.product_id == p.id, MarketplaceSKU.active.is_(True))).all()
        offers = []
        for sku in skus:
            offer = self.db.scalar(select(MarketplaceOffer).where(MarketplaceOffer.sku_id == sku.id,
                                                                   MarketplaceOffer.seller_tenant_id == p.seller_tenant_id,
                                                                   MarketplaceOffer.status == 'active'))
            if offer:
                listing = self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.offer_id == offer.id,
                                                                            MarketplaceListing.status == 'published',
                                                                            MarketplaceListing.moderation_status == 'approved'))
                if listing:
                    offers.append({'offer_id': offer.id, 'sku_id': sku.id, 'sku_code': sku.sku_code,
                                   'sku_name': sku.name, 'attributes': json.loads(sku.attributes_json or '{}'),
                                   'listing_id': listing.id, 'currency': offer.currency,
                                   'unit_price': str(offer.unit_price), 'stock_policy': offer.stock_policy})
        return {'id': p.id, 'slug': p.slug, 'name': p.name, 'description': p.description, 'brand': p.brand,
                'category_id': p.category_id,
                'seller': {'tenant_id': seller.tenant_id, 'slug': seller.slug, 'display_name': seller.display_name},
                'offers': offers}
