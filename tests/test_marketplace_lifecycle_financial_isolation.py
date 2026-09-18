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


def test_seller_balance_is_credited_once_and_debited_on_payout():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-BAL-1')
    db.commit()
    assert m.seller_balance(seller.id, payout.market_id, payout.currency) == {'YER': str(payout.net_amount)}
    m.set_payout_destination(seller.id, 'test-provider', 'DEST-BAL')
    m.verify_payout_destination(seller.id, admin.id)
    payout.payment_reference = 'PAY-BAL'
    payout.settlement_reference = 'SET-BAL-1'
    db.commit()
    m.request_payout(seller.id, o.id)
    m.mark_payout_paid(seller.id, o.id, 'EXT-BAL-1')
    assert m.seller_balance(seller.id, payout.market_id, payout.currency) == {'YER': '0.0000'}


def test_eligible_refund_reverses_seller_balance():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-BAL-2')
    db.commit()
    rr = m.request_return(buyer.id, o.id, 'damaged', 'damage')
    m.review_return(seller.id, rr.id, 'approved')
    m.advance_return(seller.id, rr.id, 'pickup')
    m.advance_return(seller.id, rr.id, 'received')
    m.advance_return(seller.id, rr.id, 'inspected')
    m.approve_refund(seller.id, rr.id)
    m.complete_return_refund(seller.id, rr.id, 'PR-BAL-2')
    assert m.seller_balance(seller.id, payout.market_id, payout.currency) == {'YER': '0.0000'}


def test_seller_statement_has_running_balance_and_period_totals():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-STATEMENT')
    db.commit()
    statement = m.seller_statement(seller.id, payout.market_id, payout.currency)
    assert statement['opening_balance'] == '0.0000'
    assert statement['credits'] == str(payout.net_amount)
    assert statement['payouts'] == '0.0000'
    assert statement['available_balance'] == str(payout.net_amount)
    assert statement['items'][-1]['running_balance'] == str(payout.net_amount)


def test_paid_payout_refund_creates_recoverable_balance_debit_once():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'paid'
    payout.paid_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    payout.net_amount = Decimal('950.0000')
    db.commit()
    rr = m.request_return(buyer.id, o.id, 'damaged', 'post-payout')
    m.review_return(seller.id, rr.id, 'approved')
    m.advance_return(seller.id, rr.id, 'pickup')
    m.advance_return(seller.id, rr.id, 'received')
    m.advance_return(seller.id, rr.id, 'inspected')
    m.approve_refund(seller.id, rr.id)
    m.complete_return_refund(seller.id, rr.id, 'PR-PAID-RECOVERY')
    assert m.seller_balance(seller.id, payout.market_id, payout.currency) == {'YER': '-950.0000'}
    rows = db.scalars(select(__import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry).where(
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.entry_type == 'refund_recovery')).all()
    assert len(rows) == 1
