from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant, User
from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceFulfillment
from app.core.models.marketplace_operational import MarketplaceOrderFinancialAllocation
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from app.engines.marketplace import MarketplaceService, ListingInput

def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ids=IdentityService(db); seller1=ids.create_tenant('Seller One'); seller2=ids.create_tenant('Seller Two'); buyer_t=ids.create_tenant('Buyer')
    admin1=ids.create_user('seller1','seller1@example.com'); admin2=ids.create_user('seller2','seller2@example.com'); buyer=ids.create_user('buyer','buyer@example.com')
    ids.add_membership(admin1.id,seller1.id,'owner'); ids.add_membership(admin2.id,seller2.id,'owner'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    inv=InventoryProductionService(db)
    for seller, item in [(seller1,'rice'),(seller2,'oil')]:
        inv.create_item(seller.id,item,item.title(),'unit'); inv.create_warehouse(seller.id,f'wh-{seller.id}','Main'); inv.record(seller.id,StockMovement(item,f'wh-{seller.id}',Decimal('20'),'in','opening'))
    m=MarketplaceService(db)
    for seller,admin,slug,name in [(seller1,admin1,'seller-one','Seller One'),(seller2,admin2,'seller-two','Seller Two')]:
        m.register_seller(seller.id,slug,name); m.review_seller_verification(seller.id,admin.id,'approved')
    a=m.add_address(buyer.id,'Home','Buyer','700000000','Aden','Aden','Main street')
    listings=[]
    for seller,item,admin,title,price in [(seller1,'rice',admin1,'Rice',1000),(seller2,'oil',admin2,'Oil',1500)]:
        l=m.create_listing(seller.id,ListingInput(title.lower(),title,'','product','YER',Decimal(price),item,f'wh-{seller.id}')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id); listings.append(l)
    return db,m,buyer,a,listings

def test_multiseller_checkout_creates_one_customer_order_and_seller_orders():
    db,m,buyer,a,listings=setup()
    m.add_to_cart(buyer.id,listings[0].id,2); m.add_to_cart(buyer.id,listings[1].id,1)
    orders=m.checkout(buyer.id,a.id)
    assert len(orders)==2
    co=db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.buyer_user_id==buyer.id))
    children=db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id==co.id).order_by(MarketplaceSellerOrder.id)).all()
    fulfillments=db.scalars(select(MarketplaceFulfillment).where(MarketplaceFulfillment.seller_order_id.in_([x.id for x in children]))).all()
    assert co.total == Decimal('3500.0000')
    assert len(children)==2 and {x.seller_tenant_id for x in children}=={listings[0].seller_tenant_id,listings[1].seller_tenant_id}
    assert len(fulfillments)==2 and all(x.status=='pending' for x in fulfillments)
    allocations=db.scalars(select(MarketplaceOrderFinancialAllocation).where(MarketplaceOrderFinancialAllocation.marketplace_order_id.in_([x.id for x in orders]))).all()
    assert len(allocations)==2
    assert sum((x.gross_amount for x in allocations), Decimal('0')) == Decimal('3500.0000')
    assert sum((x.net_amount for x in allocations), Decimal('0')) == sum((x.net_amount for x in [db.scalar(select(__import__('app.core.models.marketplace', fromlist=['MarketplacePayout']).MarketplacePayout).where(__import__('app.core.models.marketplace', fromlist=['MarketplacePayout']).MarketplacePayout.marketplace_order_id==o.id)) for o in orders]), Decimal('0'))
    assert {x.seller_tenant_id for x in allocations} == {listings[0].seller_tenant_id,listings[1].seller_tenant_id}
    view=m.customer_order_view(buyer.id,co.id)
    assert view['reference']==co.reference and len(view['seller_orders'])==2

def test_customer_order_is_buyer_scoped():
    db,m,buyer,a,listings=setup(); m.add_to_cart(buyer.id,listings[0].id,1); m.checkout(buyer.id,a.id)
    co=db.scalar(select(MarketplaceCustomerOrder))
    try:
        m.customer_order_view('not-the-buyer',co.id)
        assert False
    except ValueError as exc:
        assert 'customer order not found' in str(exc)
