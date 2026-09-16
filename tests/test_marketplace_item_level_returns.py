from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.models.marketplace import MarketplaceOrderLine, MarketplaceReturnLine, MarketplaceRefundLine, MarketplaceOrder
from app.core.models.payments import PaymentIntent
from app.engines.marketplace import MarketplaceService, MarketplaceError
from tests.test_marketplace_returns_refunds import setup


def prepare_two_line_order():
    db,m,ids,seller,admin,buyer,o=setup()
    # Split the existing single line into two immutable commerce lines for the test.
    line=db.scalar(select(MarketplaceOrderLine).where(MarketplaceOrderLine.marketplace_order_id==o.id))
    line.quantity=Decimal('1'); line.line_total=Decimal('1000')
    line2=MarketplaceOrderLine(marketplace_order_id=o.id,listing_id=line.listing_id,title_snapshot='Rice second unit',quantity=Decimal('1'),unit_price=Decimal('500'),line_total=Decimal('500'))
    db.add(line2)
    o.subtotal=Decimal('1500'); o.total=Decimal('1500'); db.commit(); db.refresh(line); db.refresh(line2)
    p=db.scalar(select(PaymentIntent).where(PaymentIntent.reference==o.payment_reference)); p.amount=Decimal('1500'); db.commit()
    return db,m,ids,seller,admin,buyer,o,line,line2


def test_item_return_allows_partial_quantity_and_partial_refund():
    db,m,ids,seller,admin,buyer,o,line,line2=prepare_two_line_order()
    rr=m.request_item_return(buyer.id,o.id,[{'order_line_id':line.id,'quantity':Decimal('1')}],'damaged','one item damaged')
    rr=m.review_return(seller.id,rr.id,'approved')
    m.advance_return(seller.id,rr.id,'pickup'); m.advance_return(seller.id,rr.id,'received'); m.advance_return(seller.id,rr.id,'inspected')
    rr,refund=m.approve_refund(seller.id,rr.id)
    assert rr.refund_scope=='items' and refund.amount==Decimal('1000.0000')
    refund_line=db.scalar(select(MarketplaceRefundLine).where(MarketplaceRefundLine.payment_refund_id==refund.id))
    assert refund_line.return_line_id > 0 and refund_line.amount==Decimal('1000.0000')
    rr,refund=m.complete_return_refund(seller.id,rr.id,'PR-PARTIAL-1')
    assert rr.status=='refunded'
    order=db.get(MarketplaceOrder,o.id); assert order.status=='partially_refunded'
    payment=db.scalar(select(PaymentIntent).where(PaymentIntent.reference==o.payment_reference)); assert payment.status=='captured'


def test_item_return_cannot_exceed_remaining_quantity_across_returns():
    db,m,ids,seller,admin,buyer,o,line,line2=prepare_two_line_order()
    rr=m.request_item_return(buyer.id,o.id,[{'order_line_id':line.id,'quantity':Decimal('1')}],'damaged','first')
    m.review_return(seller.id,rr.id,'rejected')
    # Rejected returns release the quantity.
    rr2=m.request_item_return(buyer.id,o.id,[{'order_line_id':line.id,'quantity':Decimal('1')}],'damaged','second')
    assert rr2.id != rr.id
    with pytest.raises(MarketplaceError):
        m.request_item_return(buyer.id,o.id,[{'order_line_id':line.id,'quantity':Decimal('0.1') }],'damaged','third')


def test_item_return_validates_line_ownership_and_duplicates():
    db,m,ids,seller,admin,buyer,o,line,line2=prepare_two_line_order()
    with pytest.raises(MarketplaceError):
        m.request_item_return(buyer.id,o.id,[{'order_line_id':999999,'quantity':Decimal('1')}],'x','bad')
    with pytest.raises(MarketplaceError):
        m.request_item_return(buyer.id,o.id,[{'order_line_id':line.id,'quantity':Decimal('0.5')},{'order_line_id':line.id,'quantity':Decimal('0.5')}],'x','duplicate')


def test_return_view_exposes_item_lines():
    db,m,ids,seller,admin,buyer,o,line,line2=prepare_two_line_order()
    rr=m.request_item_return(buyer.id,o.id,[{'order_line_id':line2.id,'quantity':Decimal('1')}],'wrong-size','size issue')
    view=m.return_view(buyer.id,rr.id)
    assert view['refund_scope']=='items' and len(view['lines'])==1 and view['lines'][0]['order_line_id']==line2.id
