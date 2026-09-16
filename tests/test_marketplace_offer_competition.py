from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.models.catalog import MarketplaceProduct, MarketplaceSKU, MarketplaceOffer
from app.core.models.marketplace import MarketplaceListing, MarketplaceOfferCompetition, MarketplaceOfferCompetitionScore
from app.core.models.inventory import InventoryMovementRecord
from app.engines.marketplace import MarketplaceService, MarketplaceError
from app.engines.catalog import CatalogService, ProductInput, SKUInput, OfferInput
from app.engines.inventory.production import InventoryProductionService
from tests.test_catalog_core import setup


def seller_with_product(db, seller_id, slug, price, shipping, days, item_id, warehouse='wh', stock=10):
    m=MarketplaceService(db)
    if not db.get(__import__('app.core.models.marketplace',fromlist=['MarketplaceSellerProfile']).MarketplaceSellerProfile,seller_id):
        m.register_seller(seller_id,slug,slug.title())
    # verification helper is called by test setup's user; use first user
    user=db.scalar(__import__('sqlalchemy').select(__import__('app.core.models.core',fromlist=['User']).User))
    m.review_seller_verification(seller_id,user.id,'approved')
    inv=InventoryProductionService(db)
    if not db.get(__import__('app.core.models.inventory',fromlist=['InventoryItem']).InventoryItem,(item_id,seller_id)):
        inv.create_item(seller_id,item_id,slug,'unit')
        if not db.get(__import__('app.core.models.inventory',fromlist=['Warehouse']).Warehouse,(warehouse,seller_id)):
            inv.create_warehouse(seller_id,warehouse,'Main')
        if stock > 0:
            db.add(InventoryMovementRecord(tenant_id=seller_id,item_id=item_id,warehouse_id=warehouse,quantity=Decimal(stock),direction='in',reference=f'STOCK-{seller_id}-{item_id}')); db.commit()
    c=CatalogService(db)
    p=c.create_product(seller_id,ProductInput(f'{slug}-product',f'Shared Widget','', 'BrandX'))
    s=c.create_sku(seller_id,p.id,SKUInput(f'{slug}-sku','Shared Widget',{},item_id))
    o=c.create_offer(seller_id,s.id,OfferInput('YER',Decimal(price),'managed',warehouse,Decimal(shipping),days))
    l=c.create_listing(seller_id,o.id,slug=f'{slug}-listing')
    m.moderate_listing(l.id,user.id,'approved'); m.publish_listing(seller_id,l.id)
    return p,o,l


def test_featured_offer_ranks_landed_price_and_persists_audit():
    db,seller=setup()
    from app.core.models.core import Tenant, User, TenantMembership
    ids=__import__('app.engines.identity',fromlist=['IdentityService']).IdentityService(db)
    seller2=ids.create_tenant('Seller2')
    p1,o1,l1=seller_with_product(db,seller.id,'seller-one',1000,100,2,'item-one')
    p2,o2,l2=seller_with_product(db,seller2.id,'seller-two',950,300,2,'item-two')
    m=MarketplaceService(db); group=m.set_catalog_group(seller.id,p1.id,'shared-widget-v1'); m.set_catalog_group(seller2.id,p2.id,'shared-widget-v1')
    result=m.offer_competition(group.id,'YER')
    assert result['featured_offer_id']==o1.id
    assert result['offers'][0]['rank']==1 and result['offers'][0]['featured'] is True
    assert result['offers'][0]['unit_price']=='1000.0000'
    scores=db.scalars(select(MarketplaceOfferCompetitionScore).order_by(MarketplaceOfferCompetitionScore.rank)).all()
    assert len(scores)==2 and scores[0].offer_id==o1.id
    comp=db.scalar(select(MarketplaceOfferCompetition).where(MarketplaceOfferCompetition.catalog_group_id==group.id))
    assert comp and comp.featured_offer_id==o1.id


def test_featured_offer_excludes_out_of_stock():
    db,seller=setup()
    from app.core.models.core import User
    ids=__import__('app.engines.identity',fromlist=['IdentityService']).IdentityService(db)
    seller2=ids.create_tenant('Seller2')
    p1,o1,l1=seller_with_product(db,seller.id,'seller-one','500',0,1,'item-one',stock=0)
    p2,o2,l2=seller_with_product(db,seller2.id,'seller-two','700',0,5,'item-two',stock=5)
    m=MarketplaceService(db); m.set_catalog_group(seller.id,p1.id,'stock-widget'); group=m.set_catalog_group(seller2.id,p2.id,'stock-widget')
    result=m.offer_competition(group.id,'YER')
    assert result['featured_offer_id']==o2.id
    assert len(result['offers'])==1


def test_no_eligible_offers_fails_closed():
    db,seller=setup(); m=MarketplaceService(db)
    from app.core.models.catalog import MarketplaceCatalogGroup
    g=MarketplaceCatalogGroup(catalog_key='empty',title='Empty'); db.add(g); db.commit()
    with pytest.raises(MarketplaceError,match='no eligible offers'):
        m.offer_competition(g.id,'YER')
