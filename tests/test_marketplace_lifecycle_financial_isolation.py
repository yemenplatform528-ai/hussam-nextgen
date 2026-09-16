from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.models.marketplace import MarketplacePayout, MarketplaceReturnRequest, MarketplaceDispute
from app.engines.marketplace import MarketplaceError
from tests.test_marketplace_returns_refunds import setup
from tests.test_marketplace_item_level_returns import prepare_two_line_order


def test_lifecycle_aggregates_inherit_order_market():
    db, m, ids, seller, admin, buyer, o = setup()
    rr = m.request_return(buyer.id, o.id, 'damaged', 'damage')
    d = m.open_dispute(buyer.id, o.id, 'not-as-described', 'details') if False else None
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    assert o.market_id is not None
    assert rr.market_id == o.market_id
    assert payout.market_id == o.market_id


def test_dispute_inherits_order_market():
    db, m, ids, seller, admin, buyer, o = setup()
    d = m.open_dispute(buyer.id, o.id, 'not-as-described', 'details')
    assert d.market_id == o.market_id


def test_full_refund_reverses_unpaid_payout_and_blocks_payout():
    db, m, ids, seller, admin, buyer, o = setup()
    rr = m.request_return(buyer.id, o.id, 'damaged', 'damage')
    m.review_return(seller.id, rr.id, 'approved')
    m.advance_return(seller.id, rr.id, 'pickup')
    m.advance_return(seller.id, rr.id, 'received')
    m.advance_return(seller.id, rr.id, 'inspected')
    m.approve_refund(seller.id, rr.id)
    m.complete_return_refund(seller.id, rr.id, 'PR-FULL-LIFECYCLE')
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    assert payout.status == 'reversed'
    assert payout.net_amount == Decimal('0.0000')
    with pytest.raises(MarketplaceError):
        m.payout_eligible(seller.id, o.id)


def test_partial_refund_reduces_unpaid_payout():
    db, m, ids, seller, admin, buyer, o, line, line2 = prepare_two_line_order()
    rr = m.request_item_return(buyer.id, o.id, [{'order_line_id': line2.id, 'quantity': Decimal('1')}], 'damaged', 'partial')
    m.review_return(seller.id, rr.id, 'approved')
    m.advance_return(seller.id, rr.id, 'pickup')
    m.advance_return(seller.id, rr.id, 'received')
    m.advance_return(seller.id, rr.id, 'inspected')
    m.approve_refund(seller.id, rr.id)
    m.complete_return_refund(seller.id, rr.id, 'PR-PARTIAL-LIFECYCLE')
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    assert payout.status == 'held'
    assert payout.gross_amount == Decimal('500.0000')
    assert payout.net_amount == Decimal('450.0000')
