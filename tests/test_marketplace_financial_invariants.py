from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.models.marketplace import MarketplaceOrder, MarketplacePayout
from app.core.models.marketplace_operational import MarketplaceOrderFinancialAllocation
from app.engines.marketplace import MarketplaceError
from tests.test_marketplace_order_network import setup


def test_financial_invariants_conserve_multiseller_order():
    db, m, buyer, address, listings = setup()
    m.add_to_cart(buyer.id, listings[0].id, 2)
    m.add_to_cart(buyer.id, listings[1].id, 1)
    orders = m.checkout(buyer.id, address.id)
    for order in orders:
        report = m.assert_financial_invariants(order.id)
        assert all(report['checks'].values())


def test_financial_invariants_detect_allocation_drift():
    db, m, buyer, address, listings = setup()
    m.add_to_cart(buyer.id, listings[0].id, 1)
    order = m.checkout(buyer.id, address.id)[0]
    order.total = Decimal(str(order.total)) + Decimal('1.0000')
    db.flush()
    with pytest.raises(MarketplaceError, match='financial invariant violation'):
        m.assert_financial_invariants(order.id)

@pytest.mark.parametrize(
    ('field', 'value', 'message', 'paired'),
    [
        ('seller_tenant_id', 999999, 'allocation_seller_matches_order', {}),
        ('currency', 'USD', 'allocation_currency_matches_order', {}),
        ('platform_fee', Decimal('0'), 'allocation_fee_matches_order', {'net_amount': Decimal('1000')}),
        ('discount_amount', Decimal('1'), 'allocation_discount_matches_authority', {'net_amount': Decimal('974')}),
    ],
)
def test_financial_invariants_reject_adversarial_allocation_drift(field, value, message, paired):
    db, m, buyer, address, listings = setup()
    m.add_to_cart(buyer.id, listings[0].id, 1)
    order = m.checkout(buyer.id, address.id)[0]
    allocation = db.scalar(select(MarketplaceOrderFinancialAllocation).where(
        MarketplaceOrderFinancialAllocation.marketplace_order_id == order.id
    ))
    setattr(allocation, field, value)
    for paired_field, paired_value in paired.items():
        setattr(allocation, paired_field, paired_value)
    db.flush()
    with pytest.raises(MarketplaceError, match=message):
        m.assert_financial_invariants(order.id)


def test_multiseller_financial_invariants_cover_every_child_order_without_cross_seller_leakage():
    db, m, buyer, address, listings = setup()
    m.add_to_cart(buyer.id, listings[0].id, 2)
    m.add_to_cart(buyer.id, listings[1].id, 1)
    orders = m.checkout(buyer.id, address.id)

    reports = [m.assert_financial_invariants(order.id) for order in orders]
    assert len(reports) == 2
    assert all(all(report['checks'].values()) for report in reports)

    allocations = db.scalars(select(MarketplaceOrderFinancialAllocation).where(
        MarketplaceOrderFinancialAllocation.marketplace_order_id.in_([o.id for o in orders])
    )).all()
    assert sum((Decimal(str(a.net_amount)) for a in allocations), Decimal('0')) == sum(
        (Decimal(str(r['allocation_net'])) for r in reports), Decimal('0')
    )
    assert len({(a.seller_tenant_id, a.market_id, a.currency) for a in allocations}) == 2


def test_financial_invariants_reject_discount_scope_leakage():
    db, m, buyer, address, listings = setup()
    m.add_to_cart(buyer.id, listings[0].id, 1)
    order = m.checkout(buyer.id, address.id)[0]
    from app.core.models.marketplace import MarketplaceSellerOrder
    from app.core.models.marketplace_operational import MarketplaceDiscountAllocation
    seller_order = db.scalar(select(MarketplaceSellerOrder).where(
        MarketplaceSellerOrder.marketplace_order_id == order.id
    ))
    db.add(MarketplaceDiscountAllocation(
        customer_order_id=order.customer_order_id,
        seller_order_id=seller_order.id,
        seller_tenant_id=999999,
        amount=Decimal('10.0000'),
        currency='USD',
    ))
    db.flush()
    with pytest.raises(MarketplaceError, match='financial invariant violation'):
        m.assert_financial_invariants(order.id)
