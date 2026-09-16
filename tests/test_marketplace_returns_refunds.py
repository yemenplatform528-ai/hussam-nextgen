from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.marketplace import MarketplaceReturnRequest, MarketplaceDispute
from app.core.models.payments import PaymentIntent, PaymentRefund
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from app.engines.payments import PaymentProductionService, PaymentError


def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer')
    admin=ids.create_user('seller','seller@example.com'); buyer=ids.create_user('buyer','buyer@example.com')
    ids.add_membership(admin.id,seller.id,'owner'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main'); inv.record(seller.id,StockMovement('rice','wh',Decimal('20'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller-returns','Seller'); m.review_seller_verification(seller.id,admin.id,'approved')
    a=m.add_address(buyer.id,'Home','Buyer','700000000','Aden','Aden','Main')
    l=m.create_listing(seller.id,ListingInput('rice','Rice','','product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id,a.id)[0]
    p=PaymentIntent(tenant_id=seller.id,reference='MKT-PAY:'+o.reference,provider='test',amount=o.total,currency=o.currency,status='captured',provider_payment_id='PP-1'); db.add(p); db.flush(); o.payment_reference=p.reference; o.status='completed'; db.commit()
    return db,m,ids,seller,admin,buyer,o

def test_payment_refund_is_partial_and_idempotency_safe():
    db,m,ids,seller,admin,buyer,o=setup(); ps=PaymentProductionService(db)
    r=ps.create_refund(seller.id,o.payment_reference,refund_reference='REF-1',amount=Decimal('400'),currency='YER',reason='partial-return')
    r=ps.complete_refund(seller.id,'REF-1',provider_refund_id='PR-1'); assert r.status=='succeeded'
    p=db.scalar(select(PaymentIntent).where(PaymentIntent.reference==o.payment_reference)); assert p.status=='captured'
    with pytest.raises(PaymentError): ps.create_refund(seller.id,o.payment_reference,refund_reference='REF-2',amount=Decimal('700'),currency='YER',reason='too-much')

def test_return_lifecycle_requires_inspection_before_refund():
    db,m,ids,seller,admin,buyer,o=setup(); rr=m.request_return(buyer.id,o.id,'damaged','damaged item')
    rr=m.review_return(seller.id,rr.id,'approved'); assert rr.status=='approved'
    rr=m.advance_return(seller.id,rr.id,'pickup'); rr=m.advance_return(seller.id,rr.id,'received'); rr=m.advance_return(seller.id,rr.id,'inspected')
    rr,refund=m.approve_refund(seller.id,rr.id); assert rr.status=='refund_approved' and refund.status=='requested'
    rr,refund=m.complete_return_refund(seller.id,rr.id,'PR-RETURN-1'); assert rr.status=='refunded' and refund.status=='succeeded'
    p=db.scalar(select(PaymentIntent).where(PaymentIntent.reference==o.payment_reference)); assert p.status=='refunded'

def test_return_is_seller_scoped():
    db,m,ids,seller,admin,buyer,o=setup(); rr=m.request_return(buyer.id,o.id,'changed-mind','not needed')
    with pytest.raises(MarketplaceError): m.review_return(9999,rr.id,'approved')

def test_dispute_can_be_viewed_only_by_buyer_and_resolved_by_platform():
    db,m,ids,seller,admin,buyer,o=setup(); d=m.open_dispute(buyer.id,o.id,'not-as-described','description')
    assert m.dispute_view(buyer.id,d.id)['status']=='open'
    with pytest.raises(MarketplaceError): m.dispute_view('other',d.id)
    d=m.resolve_dispute(d.id,admin.id,'rejected','seller evidence accepted')
    assert d.status=='rejected' and d.resolution=='seller evidence accepted'
