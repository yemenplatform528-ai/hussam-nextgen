from tests.market_test_support import ensure_market
from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.contracts import StockMovement
from app.core.models.marketplace import MarketplaceSellerOrder, MarketplaceCustomerOrder
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.marketplace import MarketplaceService, ListingInput
from app.engines.fulfillment import FulfillmentService, FulfillmentError


def setup_two_sellers():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)(); ensure_market(db)
    ids=IdentityService(db); buyer_t=ids.create_tenant('Buyer'); buyer=ids.create_user('buyer','buyer@example.com'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    sellers=[]
    for n in ('A','B'):
        seller=ids.create_tenant(f'Seller {n}'); admin=ids.create_user(f'seller{n.lower()}',f'seller{n.lower()}@example.com'); ids.add_membership(admin.id,seller.id,'owner')
        inv=InventoryProductionService(db); inv.create_item(seller.id,f'rice{n}','Rice','unit'); inv.create_warehouse(seller.id,f'wh{n}','Main'); inv.record(seller.id,StockMovement(f'rice{n}',f'wh{n}',Decimal('10'),'in','opening'))
        m=MarketplaceService(db); m.register_seller(seller.id,f'seller{n}',f'Seller {n}'); m.review_seller_verification(seller.id,admin.id,'approved')
        a=m.add_address(buyer.id,'Home','Buyer','700000000','Aden','Aden','Main')
        l=m.create_listing(seller.id,ListingInput(f'rice{n}','Rice','','product','YER',Decimal('1000'),f'rice{n}',f'wh{n}')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id); m.add_to_cart(buyer.id,l.id,1); sellers.append(seller)
    orders=m.checkout(buyer.id,a.id); return db,m,sellers,orders[0]


def test_delivered_requires_active_seller_order():
    db,m,sellers,order=setup_two_sellers(); so=db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==order.id, MarketplaceSellerOrder.seller_tenant_id==sellers[0].id))
    fs=FulfillmentService(db); so.status='paid'; db.commit()
    try: fs.create(sellers[0].id,so.id)
    except FulfillmentError: pass
    else: assert False


def test_one_seller_fulfilled_does_not_complete_customer_order():
    db,m,sellers,order=setup_two_sellers();
    children=db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id==order.customer_order_id)).all()
    for so in children: so.status='processing'
    db.commit(); fs=FulfillmentService(db)
    f=fs.create(sellers[0].id,children[0].id,'pickup'); fs.transition(sellers[0].id,f.id,'assigned'); fs.transition(sellers[0].id,f.id,'ready')
    # pickup is self-contained and needs no shipment.
    fs.transition(sellers[0].id,f.id,'delivered',event_id='pickup-1',note='collected')
    co=db.get(MarketplaceCustomerOrder,order.customer_order_id)
    assert co.status != 'completed'
    assert db.get(MarketplaceSellerOrder,children[1].id).status == 'processing'
