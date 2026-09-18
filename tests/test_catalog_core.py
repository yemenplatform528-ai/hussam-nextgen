from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant, User, TenantMembership, InventoryItem, Warehouse
from app.core.models.catalog import MarketplaceProduct, MarketplaceSKU, MarketplaceOffer
from app.core.models.marketplace import MarketplaceSellerProfile, MarketplaceSellerVerification, MarketplaceListing
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.catalog import CatalogService, ProductInput, SKUInput, OfferInput, CatalogError


def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); user=ids.create_user('seller','seller@example.com'); ids.add_membership(user.id,seller.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main')
    from app.core.models.market import MarketContext, MarketCurrency
    market=MarketContext(code='YE',country_code='YE',name='Yemen',locale='ar-YE',timezone='Asia/Aden',default_currency='YER',status='active')
    db.add(market); db.flush(); db.add(MarketCurrency(market_id=market.id,currency='YER',is_default=True)); db.flush()
    m=__import__('app.engines.marketplace',fromlist=['MarketplaceService']).MarketplaceService(db)
    m.register_seller(seller.id,'seller-catalog','Seller Catalog'); m.review_seller_verification(seller.id,user.id,'approved')
    return db,seller


def test_catalog_chain_product_sku_offer_listing():
    db,seller=setup(); c=CatalogService(db)
    p=c.create_product(seller.id,ProductInput('rice-10kg','Rice 10kg','Long grain','BrandX'))
    sku=c.create_sku(seller.id,p.id,SKUInput('RICE-10-BLK','Rice 10kg',{'pack':'10kg'},'rice'))
    offer=c.create_offer(seller.id,sku.id,OfferInput('YER',Decimal('2500'),'managed','wh'))
    listing=c.create_listing(seller.id,offer.id,slug='rice-10kg',title='Rice 10kg')
    assert (listing.product_id,listing.sku_id,listing.offer_id)==(p.id,sku.id,offer.id)
    assert c.seller_catalog(seller.id)[0]['skus'][0]['offer']['id']==offer.id


def test_catalog_tenant_and_inventory_boundaries():
    db,seller=setup(); c=CatalogService(db)
    p=c.create_product(seller.id,ProductInput('x','X'))
    with pytest.raises(CatalogError): c.create_sku(seller.id,p.id,SKUInput('X','X',{},'missing'))
    with pytest.raises(CatalogError): c.create_offer(seller.id,999,OfferInput('YER',1,'managed','wh'))


def test_catalog_bundle_is_atomic_on_validation_failure():
    db,seller=setup(); c=CatalogService(db)
    with pytest.raises(CatalogError):
        c.create_product_bundle(
            seller.id,
            product=ProductInput('atomic','Atomic'),
            sku=SKUInput('ATOMIC-1','Atomic',{},'missing-item'),
            offer=OfferInput('YER',Decimal('10'),'managed','wh'),
            listing_slug='atomic',
        )
    assert db.scalar(select(MarketplaceProduct).where(MarketplaceProduct.seller_tenant_id==seller.id, MarketplaceProduct.slug=='atomic')) is None


def test_catalog_identifiers_are_market_scoped():
    db, seller = setup(); c = CatalogService(db)
    from app.core.models.market import MarketContext, MarketCurrency
    c.create_product(seller.id, ProductInput('bootstrap-market','Bootstrap'))
    m1 = db.scalar(select(MarketContext).where(MarketContext.code == 'YE'))
    m2 = MarketContext(code='SA', country_code='SA', name='Saudi Arabia', locale='ar-SA', timezone='Asia/Riyadh', default_currency='SAR', status='active')
    db.add(m2); db.flush(); db.add(MarketCurrency(market_id=m2.id, currency='SAR', is_default=True)); db.commit()
    p1 = c.create_product(seller.id, ProductInput('same-slug','Same',market_id=m1.id))
    p2 = c.create_product(seller.id, ProductInput('same-slug','Same',market_id=m2.id))
    assert p1.id != p2.id
    sku1 = c.create_sku(seller.id,p1.id,SKUInput('SAME','Same',{},'rice'))
    sku2 = c.create_sku(seller.id,p2.id,SKUInput('SAME','Same',{},'rice'))
    o1 = c.create_offer(seller.id,sku1.id,OfferInput('YER',1,'managed','wh',market_id=m1.id))
    o2 = c.create_offer(seller.id,sku2.id,OfferInput('SAR',1,'managed','wh',market_id=m2.id))
    l1 = c.create_listing(seller.id,o1.id,slug='same-listing')
    l2 = c.create_listing(seller.id,o2.id,slug='same-listing')
    assert l1.id != l2.id and l1.market_id != l2.market_id
