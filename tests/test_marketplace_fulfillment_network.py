from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant, User
from app.core.models.marketplace import MarketplaceSellerOrder, MarketplaceFulfillment, MarketplacePackage, MarketplaceCustomerOrder
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from app.engines.marketplace import MarketplaceService, ListingInput
from app.engines.fulfillment import FulfillmentService, FulfillmentError

def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer')
    admin=ids.create_user('seller','seller@example.com'); buyer=ids.create_user('buyer','buyer@example.com')
    ids.add_membership(admin.id,seller.id,'owner'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','unit'); inv.create_warehouse(seller.id,'wh','Main'); inv.record(seller.id,StockMovement('rice','wh',Decimal('10'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller','Seller'); m.review_seller_verification(seller.id,admin.id,'approved')
    a=m.add_address(buyer.id,'Home','Buyer','700000000','Aden','Aden','Main')
    l=m.create_listing(seller.id,ListingInput('rice','Rice','','product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,2); orders=m.checkout(buyer.id,a.id); return db,m,ids,seller,admin,buyer,orders[0],a

def test_fulfillment_lifecycle_and_shipment():
    db,m,ids,seller,admin,buyer,order,a=setup(); m.mark_paid(seller.id,order.id,'missing') if False else None
    # Payment is not fabricated: move the seller order directly only for this focused fulfillment test.
    so=db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==order.id)); so.status='processing'; db.commit()
    fs=FulfillmentService(db); f=fs.create(seller.id,so.id,'hussam_delivery'); fs.transition(seller.id,f.id,'assigned'); fs.transition(seller.id,f.id,'ready')
    f,shipment=fs.create_shipment(seller.id,f.id,'Hussam Delivery','TRK-001')
    assert shipment.status=='ready' and f.shipment_id==shipment.id
    fs.transition(seller.id,f.id,'picked_up',event_id='evt-pick')
    fs.transition(seller.id,f.id,'in_transit',event_id='evt-transit')
    fs.transition(seller.id,f.id,'out_for_delivery',event_id='evt-out')
    fs.transition(seller.id,f.id,'delivered',event_id='evt-delivery')
    assert f.status=='delivered'
    so=db.get(MarketplaceSellerOrder,so.id); assert so.status=='fulfilled'

def test_fulfillment_is_tenant_scoped():
    db,m,ids,seller,admin,buyer,order,a=setup(); so=db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==order.id)); so.status='processing'; db.commit()
    fs=FulfillmentService(db); f=fs.create(seller.id,so.id)
    try: fs._fulfillment(9999,f.id)
    except FulfillmentError as exc: assert 'seller tenant' in str(exc)
    else: assert False

def test_package_is_tenant_scoped_and_attached_to_fulfillment():
    db,m,ids,seller,admin,buyer,order,a=setup(); so=db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==order.id)); so.status='processing'; db.commit()
    fs=FulfillmentService(db); f=fs.create(seller.id,so.id); fs.transition(seller.id,f.id,'assigned')
    p=fs.create_package(seller.id,f.id,'PKG-1',Decimal('1.250'),'sealed')
    assert p.fulfillment_id==f.id and p.status=='packed' and p.weight_kg==Decimal('1.250')
    try: fs.create_package(9999,f.id,'PKG-2')
    except FulfillmentError as exc: assert 'seller tenant' in str(exc)
    else: assert False
