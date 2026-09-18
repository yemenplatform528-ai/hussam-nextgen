from tests.market_test_support import ensure_market
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplacePaymentAllocation
from app.engines.marketplace import MarketplaceService, MarketplaceError, ListingInput
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from app.core.models.finance import FiscalPeriod


def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)(); ensure_market(db)
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer')
    admin=ids.create_user('seller','seller38@example.com'); buyer=ids.create_user('buyer','buyer38@example.com')
    ids.add_membership(admin.id,seller.id,'owner'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice38','Rice','bag'); inv.create_warehouse(seller.id,'wh38','Main'); inv.record(seller.id,StockMovement('rice38','wh38',Decimal('20'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller-pay38','Seller'); m.review_seller_verification(seller.id,admin.id,'approved')
    a=m.add_address(buyer.id,'Home','Buyer','700000000','Aden','Aden','Main')
    l=m.create_listing(seller.id,ListingInput('rice38','Rice','','product','YER',Decimal('1000'),'rice38','wh38')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,2); co=m.checkout(buyer.id,a.id)[0].customer_order_id
    db.add(FiscalPeriod(tenant_id=seller.id,name='2026',starts_on=date(2026,1,1),ends_on=date(2026,12,31),closed=False)); db.commit()
    return db,m,buyer.id,co

def test_unified_payment_session_reconciles_and_captures():
    db,m,buyer,co_id=setup(); session=m.create_payment_session(buyer,co_id,'test-provider')
    co=db.get(MarketplaceCustomerOrder,co_id); allocations=db.scalars(select(MarketplacePaymentAllocation).where(MarketplacePaymentAllocation.session_id==session.id)).all()
    assert Decimal(str(session.amount))==Decimal(str(co.total))
    assert sum((Decimal(str(x.amount)) for x in allocations),Decimal('0'))==Decimal(str(co.total))
    captured=m.capture_payment_session(buyer,co_id,'PROV-38')
    assert captured.status=='captured' and captured.provider_payment_id=='PROV-38'
    assert db.get(MarketplaceCustomerOrder,co_id).status=='paid'
    assert {x.status for x in db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id==co_id)).all()}=={'paid'}
    assert m.capture_payment_session(buyer,co_id,'PROV-38').id==session.id

def test_payment_session_rejects_conflicting_capture():
    db,m,buyer,co_id=setup(); m.create_payment_session(buyer,co_id,'test-provider'); m.capture_payment_session(buyer,co_id,'PROV-38')
    with pytest.raises(MarketplaceError,match='different provider payment id'):
        m.capture_payment_session(buyer,co_id,'PROV-OTHER')


def test_multi_seller_capture_is_atomic_when_a_later_allocation_fails():
    db,m,buyer,co_id=setup()
    session=m.create_payment_session(buyer,co_id,'test-provider')
    allocations=db.scalars(select(MarketplacePaymentAllocation).where(MarketplacePaymentAllocation.session_id==session.id).order_by(MarketplacePaymentAllocation.id)).all()
    assert len(allocations) == 1
    # Force the allocation to reference a missing marketplace order. Capture must not leave a payment intent behind.
    allocations[0].marketplace_order_id = 999999
    db.commit()
    with pytest.raises(Exception):
        m.capture_payment_session(buyer,co_id,'PROV-ATOMIC')
    db.rollback()
    assert db.query(MarketplacePaymentAllocation).filter_by(session_id=session.id).count() == 1
    from app.core.models.payments import PaymentIntent
    assert db.query(PaymentIntent).filter(PaymentIntent.reference.like(f'{session.reference}:%')).count() == 0
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.models.marketplace import MarketplacePaymentAllocation
from app.engines.marketplace import MarketplaceError
from tests.test_marketplace_payment_orchestration import setup

def test_payment_conservation_rejects_allocation_amount_drift():
    db,m,buyer,co_id=setup()
    session=m.create_payment_session(buyer,co_id,'test-provider')
    allocation=db.scalar(select(MarketplacePaymentAllocation).where(MarketplacePaymentAllocation.session_id==session.id))
    allocation.amount=Decimal(str(allocation.amount))+Decimal('1.0000')
    db.flush()
    with pytest.raises(MarketplaceError, match='payment conservation violation'):
        m.assert_payment_conservation(session.id)

def test_payment_conservation_rejects_currency_drift():
    db,m,buyer,co_id=setup()
    session=m.create_payment_session(buyer,co_id,'test-provider')
    allocation=db.scalar(select(MarketplacePaymentAllocation).where(MarketplacePaymentAllocation.session_id==session.id))
    allocation.currency='USD'
    db.flush()
    with pytest.raises(MarketplaceError, match='payment conservation violation'):
        m.assert_payment_conservation(session.id)
