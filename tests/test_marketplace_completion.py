from tests.market_test_support import ensure_market
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant, User, TenantMembership
from app.core.models.marketplace import MarketplaceSellerVerification, MarketplaceShippingQuote, MarketplaceFavorite, MarketplaceReturnRequest
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from app.engines.marketplace_completion import MarketplaceCompletionService

def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)(); ensure_market(db)
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer'); buyer=ids.create_user('buyer','buyer@example.com'); su=ids.create_user('seller','seller@example.com'); ids.add_membership(buyer.id,buyer_t.id,'owner'); ids.add_membership(su.id,seller.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main'); inv.record(seller.id,StockMovement('rice','wh',Decimal('20'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller','Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice','Rice','product','product','YER',Decimal('1000'),'rice','wh'))
    m.moderate_listing(l.id,su.id,'approved')
    m.publish_listing(seller.id,l.id); m.ensure_buyer(buyer.id); a=m.add_address(buyer.id,'home','Buyer','777','Aden','Aden','Street')
    return db,seller,buyer,su,l,a,m

def test_verification_is_required_for_activation_and_public_visibility():
    db,seller,buyer,su,l,a,m=setup()
    assert db.scalar(select(MarketplaceSellerVerification).where(MarketplaceSellerVerification.seller_tenant_id==seller.id)).status=='approved'
    assert m.public_listings()[0]['seller']['tenant_id']==seller.id

def test_shipping_quote_is_server_owned_and_consumed():
    db,seller,buyer,su,l,a,m=setup(); m.add_shipping_rate(seller.id,'Aden','Aden','YER',Decimal('250'))
    m.add_to_cart(buyer.id,l.id,1); q=m.quote_shipping(buyer.id,a.id,seller.id,'YER'); assert q.fee==Decimal('250.0000')
    orders=m.checkout(buyer.id,a.id,Decimal('0'),None,q.id); assert orders[0].shipping_fee==Decimal('250.0000'); assert q.consumed_at is not None
    m.add_to_cart(buyer.id,l.id,1)
    with pytest.raises(MarketplaceError): m.checkout(buyer.id,a.id,Decimal('250'),500,q.id)

def test_client_cannot_supply_arbitrary_shipping_fee():
    db,seller,buyer,su,l,a,m=setup(); m.add_to_cart(buyer.id,l.id,1)
    with pytest.raises(MarketplaceError): m.checkout(buyer.id,a.id,Decimal('10'),500)

def test_payment_intent_is_attached_to_marketplace_order():
    db,seller,buyer,su,l,a,m=setup(); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id,a.id)[0]
    p=m.attach_payment_intent(buyer.id,o.id,'test-provider'); assert o.payment_reference==p.reference
    assert p.reference.startswith('MKT-PAY:')

def test_paid_order_cannot_be_directly_cancelled():
    db,seller,buyer,su,l,a,m=setup(); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id,a.id)[0]; o.status='paid'; db.commit()
    with pytest.raises(MarketplaceError): m.cancel(buyer.id,o.id)

def test_favorite_and_return_request_are_buyer_scoped():
    db,seller,buyer,su,l,a,m=setup(); f=m.add_favorite(buyer.id,l.id); assert f.listing_id==l.id; m.remove_favorite(buyer.id,l.id); assert db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.buyer_user_id==buyer.id)) is None
    m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id,a.id)[0]; o.status='completed'; db.commit(); r=m.request_return(buyer.id,o.id,'damaged','damaged item'); assert r.status=='requested'

def test_multi_seller_checkout_accepts_one_shipping_quote_per_seller():
    db,seller,buyer,su,l,a,m=setup()
    seller2_t=IdentityService(db).create_tenant('Seller Two')
    su2=IdentityService(db).create_user('seller2','seller2@example.com')
    IdentityService(db).add_membership(su2.id,seller2_t.id,'owner')
    m.register_seller(seller2_t.id,'seller-two','Seller Two'); m.review_seller_verification(seller2_t.id,su2.id,'approved')
    inv=InventoryProductionService(db); inv.create_item(seller2_t.id,'tea','Tea','bag'); inv.create_warehouse(seller2_t.id,'wh2','Main'); inv.record(seller2_t.id,StockMovement('tea','wh2',Decimal('20'),'in','opening'))
    l2=m.create_listing(seller2_t.id,ListingInput('tea','Tea','product','product','YER',Decimal('500'),'tea','wh2')); m.moderate_listing(l2.id,su2.id,'approved'); m.publish_listing(seller2_t.id,l2.id)
    m.add_shipping_rate(seller.id,'Aden','Aden','YER',Decimal('250')); m.add_shipping_rate(seller2_t.id,'Aden','Aden','YER',Decimal('150'))
    m.add_to_cart(buyer.id,l.id,1); m.add_to_cart(buyer.id,l2.id,1)
    q1=m.quote_shipping(buyer.id,a.id,seller.id,'YER'); q2=m.quote_shipping(buyer.id,a.id,seller2_t.id,'YER')
    orders=m.checkout(buyer.id,a.id,Decimal('0'),None,None,[q1.id,q2.id])
    assert len(orders)==2 and all(o.shipping_fee in {Decimal('250.0000'),Decimal('150.0000')} for o in orders)
    assert q1.consumed_at is not None and q2.consumed_at is not None


def test_checkout_discount_allocates_atomically_across_seller_orders():
    db,seller,buyer,su,l,a,m=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceOrder
    customer=MarketplaceCustomerOrder(reference='co-alloc',buyer_user_id=buyer.id,currency='YER',subtotal=Decimal('3000'),shipping_fee=Decimal('0'),total=Decimal('3000'))
    db.add(customer); db.flush()
    seller2=IdentityService(db).create_tenant('Seller Three')
    mo1=MarketplaceOrder(reference='mo-alloc-1',buyer_user_id=buyer.id,seller_tenant_id=seller.id,customer_order_id=customer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,platform_fee=0,total=Decimal('1000'))
    mo2=MarketplaceOrder(reference='mo-alloc-2',buyer_user_id=buyer.id,seller_tenant_id=seller2.id,customer_order_id=customer.id,currency='YER',subtotal=Decimal('2000'),shipping_fee=0,platform_fee=0,total=Decimal('2000'))
    db.add_all([mo1,mo2]); db.flush()
    so1=MarketplaceSellerOrder(customer_order_id=customer.id,marketplace_order_id=mo1.id,seller_tenant_id=seller.id,subtotal=Decimal('1000'),shipping_fee=0,total=1000)
    so2=MarketplaceSellerOrder(customer_order_id=customer.id,marketplace_order_id=mo2.id,seller_tenant_id=seller2.id,subtotal=Decimal('2000'),shipping_fee=0,total=2000)
    db.add_all([so1,so2]); db.commit(); db.refresh(so1); db.refresh(so2)
    out=svc.allocate_order_discount(customer.id,[{'seller_order_id':so1.id,'amount':100},{'seller_order_id':so2.id,'amount':200}],funding_source='platform')
    assert out['discount']=='300.0000' and len(out['allocations'])==2


def test_repricing_job_lifecycle():
    db,seller,buyer,su,l,a,m=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    job=svc.schedule_repricing(seller.id,l.id,now)
    assert job.status=='queued'
    out=svc.execute_repricing_job(seller.id,job.id)
    assert out['status']=='completed'

def test_discount_funding_source_is_explicit_for_platform_and_shared():
    db,seller,buyer,su,l,a,m=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceOrder
    from app.core.models.marketplace_operational import MarketplaceDiscountAllocation
    customer=MarketplaceCustomerOrder(reference='co-funding',buyer_user_id=buyer.id,currency='YER',subtotal=Decimal('3000'),shipping_fee=0,total=Decimal('3000'))
    db.add(customer); db.flush()
    mo=MarketplaceOrder(reference='mo-funding',buyer_user_id=buyer.id,seller_tenant_id=seller.id,customer_order_id=customer.id,currency='YER',subtotal=Decimal('3000'),shipping_fee=0,platform_fee=0,total=Decimal('3000'))
    db.add(mo); db.flush()
    so=MarketplaceSellerOrder(customer_order_id=customer.id,marketplace_order_id=mo.id,seller_tenant_id=seller.id,subtotal=Decimal('3000'),shipping_fee=0,total=Decimal('3000'))
    db.add(so); db.flush()
    out=svc.allocate_order_discount(customer.id,[{'seller_order_id':so.id,'amount':300}],funding_source='platform')
    row=db.scalar(select(MarketplaceDiscountAllocation).where(MarketplaceDiscountAllocation.id==out['allocations'][0]['seller_order_id'])) if False else db.scalar(select(MarketplaceDiscountAllocation).where(MarketplaceDiscountAllocation.customer_order_id==customer.id))
    assert row.seller_funded_amount == Decimal('0.0000') and row.platform_funded_amount == Decimal('300.0000')


def test_shared_discount_requires_explicit_funding_split():
    db,seller,buyer,su,l,a,m=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceOrder
    customer=MarketplaceCustomerOrder(reference='co-shared',buyer_user_id=buyer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,total=Decimal('1000'))
    db.add(customer); db.flush(); mo=MarketplaceOrder(reference='mo-shared',buyer_user_id=buyer.id,seller_tenant_id=seller.id,customer_order_id=customer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,platform_fee=0,total=Decimal('1000')); db.add(mo); db.flush(); so=MarketplaceSellerOrder(customer_order_id=customer.id,marketplace_order_id=mo.id,seller_tenant_id=seller.id,subtotal=Decimal('1000'),shipping_fee=0,total=Decimal('1000')); db.add(so); db.commit()
    with pytest.raises(Exception, match='shared discount funding requires'):
        svc.allocate_order_discount(customer.id,[{'seller_order_id':so.id,'amount':100}],funding_source='shared')
    out=svc.allocate_order_discount(customer.id,[{'seller_order_id':so.id,'amount':100,'seller_amount':40,'platform_amount':60}],funding_source='shared')
    assert out['discount']=='100.0000'


def test_platform_funded_discount_does_not_reduce_seller_payout_snapshot():
    db,seller,buyer,su,l,a,m=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceOrder, MarketplacePayout
    customer=MarketplaceCustomerOrder(reference='co-platform-payout',buyer_user_id=buyer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,total=Decimal('1000'))
    db.add(customer); db.flush()
    mo=MarketplaceOrder(reference='mo-platform-payout',buyer_user_id=buyer.id,seller_tenant_id=seller.id,customer_order_id=customer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,platform_fee=Decimal('50'),total=Decimal('1000'))
    db.add(mo); db.flush()
    so=MarketplaceSellerOrder(customer_order_id=customer.id,marketplace_order_id=mo.id,seller_tenant_id=seller.id,subtotal=Decimal('1000'),shipping_fee=0,total=Decimal('1000'))
    db.add(so); db.flush()
    payout=MarketplacePayout(market_id=mo.market_id,seller_tenant_id=seller.id,marketplace_order_id=mo.id,reference='P-PLATFORM',gross_amount=Decimal('1000'),seller_funded_discount=0,platform_funded_discount=0,platform_fee=Decimal('50'),net_amount=Decimal('950'),currency='YER',status='held')
    db.add(payout); db.commit()
    out=svc.allocate_order_discount(customer.id,[{'seller_order_id':so.id,'amount':Decimal('100')}],funding_source='platform')
    db.refresh(payout); db.refresh(mo); db.refresh(so); db.refresh(customer)
    assert out['discount']=='100.0000'
    assert customer.total == Decimal('900.0000')
    assert mo.total == Decimal('900.0000') and so.total == Decimal('900.0000')
    assert payout.seller_funded_discount == Decimal('0.0000')
    assert payout.platform_funded_discount == Decimal('100.0000')
    assert payout.net_amount == Decimal('950.0000')


def test_seller_funded_discount_reduces_seller_payout_snapshot():
    db,seller,buyer,su,l,a,m=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceOrder, MarketplacePayout
    customer=MarketplaceCustomerOrder(reference='co-seller-payout',buyer_user_id=buyer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,total=Decimal('1000'))
    db.add(customer); db.flush()
    mo=MarketplaceOrder(reference='mo-seller-payout',buyer_user_id=buyer.id,seller_tenant_id=seller.id,customer_order_id=customer.id,currency='YER',subtotal=Decimal('1000'),shipping_fee=0,platform_fee=Decimal('50'),total=Decimal('1000'))
    db.add(mo); db.flush()
    so=MarketplaceSellerOrder(customer_order_id=customer.id,marketplace_order_id=mo.id,seller_tenant_id=seller.id,subtotal=Decimal('1000'),shipping_fee=0,total=Decimal('1000'))
    db.add(so); db.flush()
    payout=MarketplacePayout(market_id=mo.market_id,seller_tenant_id=seller.id,marketplace_order_id=mo.id,reference='P-SELLER',gross_amount=Decimal('1000'),seller_funded_discount=0,platform_funded_discount=0,platform_fee=Decimal('50'),net_amount=Decimal('950'),currency='YER',status='held')
    db.add(payout); db.commit()
    svc.allocate_order_discount(customer.id,[{'seller_order_id':so.id,'amount':Decimal('100')}],funding_source='seller')
    db.refresh(payout); db.refresh(customer)
    assert customer.total == Decimal('900.0000')
    assert payout.seller_funded_discount == Decimal('100.0000')
    assert payout.platform_funded_discount == Decimal('0.0000')
    assert payout.net_amount == Decimal('850.0000')


def test_yemen_checkout_context_and_authoritative_checkout_share_market_and_quote():
    db,seller,buyer,su,l,a,m=setup()
    m.add_shipping_rate(seller.id,'Aden','Aden','YER',Decimal('250'))
    m.add_to_cart(buyer.id,l.id,1)
    q=m.quote_shipping(buyer.id,a.id,seller.id,'YER')
    from app.core.services.yemen_checkout_context import YemenCheckoutContextService
    context=YemenCheckoutContextService(db).build('YEM', user_id=buyer.id, address_id=a.id, seller_tenant_ids=[seller.id])
    assert context['market']['code']=='YEM'
    assert context['money']['currency']=='YER'
    assert context['money']['conversion']['automatic_conversion'] is False
    assert context['delivery']['destination']['coverage'] in {'available','active'}
    assert context['sellers'][0]['delivery']['available'] is True
    orders=m.checkout(buyer.id, a.id, Decimal('0'), None, q.id, None)
    assert len(orders)==1
    assert orders[0].currency=='YER'
    assert orders[0].shipping_fee==Decimal('250.0000')
    assert q.consumed_at is not None
