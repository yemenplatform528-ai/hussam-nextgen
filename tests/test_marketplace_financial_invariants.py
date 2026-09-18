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
