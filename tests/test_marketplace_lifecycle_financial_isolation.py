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
    assert payout.net_amount == Decimal('475.0000')


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
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-PAID-RECOVERY')
    db.commit()
    m.set_payout_destination(seller.id, 'test-provider', 'DEST-PAID-RECOVERY')
    m.verify_payout_destination(seller.id, admin.id)
    payout.payment_reference = 'PAY-PAID-RECOVERY'
    payout.settlement_reference = 'SET-PAID-RECOVERY'
    db.commit()
    m.request_payout(seller.id, o.id)
    m.mark_payout_paid(seller.id, o.id, 'EXT-PAID-RECOVERY')
    rr = m.request_return(buyer.id, o.id, 'damaged', 'post-payout')
    m.review_return(seller.id, rr.id, 'approved')
    m.advance_return(seller.id, rr.id, 'pickup')
    m.advance_return(seller.id, rr.id, 'received')
    m.advance_return(seller.id, rr.id, 'inspected')
    m.approve_refund(seller.id, rr.id)
    m.complete_return_refund(seller.id, rr.id, 'PR-PAID-RECOVERY')
    assert m.seller_balance(seller.id, payout.market_id, payout.currency) == {'YER': f'-{payout.net_amount:.4f}'}
    rows = db.scalars(select(__import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry).where(
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.entry_type == 'refund_recovery')).all()
    assert len(rows) == 1


def test_captured_payment_from_another_market_cannot_pay_order():
    from app.core.models.market import MarketContext
    from app.core.models.payments import PaymentIntent
    from app.engines.marketplace import MarketplaceError
    db, m, ids, seller, admin, buyer, o = setup()
    o.status='pending_payment'; db.commit()
    other = MarketContext(code='ALT', country_code='AA', name='Alt Market', locale='en-AA', timezone='UTC', default_currency='YER', status='active')
    db.add(other); db.flush(); db.commit()
    p = PaymentIntent(tenant_id=seller.id, reference='PAY-CROSS-MARKET', provider='test-provider', amount=o.total, currency=o.currency,
                      status='captured', provider_payment_id='PP-CROSS', metadata_json='{"market_id": %d}' % other.id)
    db.add(p); db.commit()
    with pytest.raises(MarketplaceError, match='payment market'):
        m.mark_paid(seller.id, o.id, p.reference)


def test_unreconciled_settlement_cannot_release_marketplace_payout():
    from app.core.models.payments import PaymentIntent, PaymentSettlement
    from app.engines.marketplace import MarketplaceError
    db, m, ids, seller, admin, buyer, o = setup()
    p = PaymentIntent(tenant_id=seller.id, reference='PAY-SET-PENDING', provider='test-provider', amount=o.total, currency=o.currency,
                      status='captured', provider_payment_id='PP-SET-PENDING', metadata_json='{\"market_id\": %d}' % o.market_id)
    db.add(p); db.flush()
    settlement = PaymentSettlement(tenant_id=seller.id, provider='test-provider', market_id=o.market_id,
                                   settlement_reference='SET-PENDING', payment_reference=p.reference,
                                   amount=o.total, currency=o.currency, status='settled', reconciliation_status='pending')
    db.add(settlement); db.commit()
    o.status='paid'; o.payment_reference=p.reference; db.commit()
    with pytest.raises(MarketplaceError, match='reconciliation is not closed'):
        m.settle_order_payment(seller.id, o.id, settlement.settlement_reference)


def test_settlement_from_another_market_cannot_link_to_order():
    from app.core.models.market import MarketContext
    from app.core.models.payments import PaymentIntent, PaymentSettlement
    from app.engines.marketplace import MarketplaceError
    db, m, ids, seller, admin, buyer, o = setup()
    p = PaymentIntent(tenant_id=seller.id, reference='PAY-SET-CROSS', provider='test-provider', amount=o.total, currency=o.currency,
                      status='captured', provider_payment_id='PP-SET-CROSS', metadata_json='{"market_id": %d}' % o.market_id)
    db.add(p); db.flush()
    other = MarketContext(code='ALT2', country_code='BB', name='Alt Market 2', locale='en-BB', timezone='UTC', default_currency='YER', status='active')
    db.add(other); db.flush()
    settlement = PaymentSettlement(tenant_id=seller.id, provider='test-provider', market_id=other.id,
                                   settlement_reference='SET-CROSS', payment_reference=p.reference,
                                   amount=o.total, currency=o.currency, status='settled')
    db.add(settlement); db.commit()
    o.status='paid'; o.payment_reference=p.reference; db.commit()
    with pytest.raises(MarketplaceError, match='settlement market'):
        m.settle_order_payment(seller.id, o.id, settlement.settlement_reference)


def test_paid_payout_refund_completion_is_idempotent_for_same_provider_reference():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-IDEMP-RECOVERY')
    db.commit()
    m.set_payout_destination(seller.id, 'test-provider', 'DEST-IDEMP-RECOVERY')
    m.verify_payout_destination(seller.id, admin.id)
    payout.payment_reference = 'PAY-IDEMP-RECOVERY'
    payout.settlement_reference = 'SET-IDEMP-RECOVERY'
    db.commit()
    m.request_payout(seller.id, o.id)
    m.mark_payout_paid(seller.id, o.id, 'EXT-IDEMP-RECOVERY')
    rr = m.request_return(buyer.id, o.id, 'damaged', 'idempotent completion')
    m.review_return(seller.id, rr.id, 'approved')
    m.advance_return(seller.id, rr.id, 'pickup')
    m.advance_return(seller.id, rr.id, 'received')
    m.advance_return(seller.id, rr.id, 'inspected')
    m.approve_refund(seller.id, rr.id)
    m.complete_return_refund(seller.id, rr.id, 'PR-IDEMP-RECOVERY')
    x, r = m.complete_return_refund(seller.id, rr.id, 'PR-IDEMP-RECOVERY')
    assert x.status == 'refunded'
    assert r.status == 'succeeded'
    rows = db.scalars(select(__import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry).where(
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.entry_type == 'refund_recovery')).all()
    assert len(rows) == 1


def test_dispute_resolution_does_not_bypass_refund_or_payout_financial_controls():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-DISPUTE-BOUNDARY')
    db.commit()

    dispute = m.open_dispute(buyer.id, o.id, 'not-as-described', 'financial boundary')
    assert dispute.status == 'open'
    assert payout.status == 'eligible'
    with pytest.raises(MarketplaceError):
        m.payout_eligible(seller.id, o.id)

    available_before = m._available_balance_amount(seller.id, payout.market_id, payout.currency)
    resolved = m.resolve_dispute(dispute.id, admin.id, 'resolved', 'review completed; financial action handled separately')
    assert resolved.status == 'resolved'

    db.refresh(payout)
    assert payout.status == 'eligible'
    assert m._available_balance_amount(seller.id, payout.market_id, payout.currency) == available_before


def test_dispute_after_paid_payout_does_not_create_implicit_recovery():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    payout.payment_reference = 'PAY-DISPUTE-PAID'
    payout.settlement_reference = 'SET-DISPUTE-PAID'
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:SET-DISPUTE-PAID')
    db.commit()
    m.set_payout_destination(seller.id, 'test-provider', 'DEST-DISPUTE-PAID')
    m.verify_payout_destination(seller.id, admin.id)
    m.request_payout(seller.id, o.id)
    m.mark_payout_paid(seller.id, o.id, 'EXT-DISPUTE-PAID')

    dispute = m.open_dispute(buyer.id, o.id, 'not-as-described', 'post-payout dispute')
    assert dispute.status == 'open'
    assert payout.status == 'paid'
    assert db.scalars(select(__import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry).where(
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
        __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry.entry_type == 'refund_recovery'
    )).all() == []


def test_seller_balance_conservation_rejects_duplicate_credit():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'eligible'
    payout.eligible_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:CONSERVE-1')
    duplicate = __import__('app.core.models.marketplace', fromlist=['MarketplaceSellerBalanceEntry']).MarketplaceSellerBalanceEntry(
        market_id=payout.market_id, seller_tenant_id=payout.seller_tenant_id, marketplace_payout_id=payout.id,
        entry_type='credit', amount=payout.net_amount, currency=payout.currency,
        reference='SBAL:DUPLICATE', source_reference='settlement:CONSERVE-2')
    db.add(duplicate)
    db.flush()
    from app.engines.marketplace import MarketplaceError
    with pytest.raises(MarketplaceError, match='duplicate credit'):
        m.assert_seller_balance_conservation(payout)


def test_seller_balance_conservation_requires_paid_payout_debit():
    db, m, ids, seller, admin, buyer, o = setup()
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
    payout.status = 'paid'
    m._balance_entry(payout, 'credit', payout.net_amount, 'settlement:CONSERVE-PAID')
    db.commit()
    from app.engines.marketplace import MarketplaceError
    with pytest.raises(MarketplaceError, match='paid payout seller balance debit'):
        m.assert_seller_balance_conservation(payout)
