from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.commerce import CommerceProductionService, CommerceError, OrderLineInput
from app.core.contracts import StockMovement
from app.core.models.commerce import SalesOrder, SalesOrderLine
from app.core.models.inventory import InventoryReservation, InventoryMovementRecord


def db():
    _, factory = make_session_factory(); return factory()


def setup():
    s = db(); t = IdentityService(s).create_tenant('Commerce Tenant')
    inv = InventoryProductionService(s)
    inv.create_item(t.id, 'item-1', 'Item 1')
    inv.create_item(t.id, 'item-2', 'Item 2')
    inv.create_warehouse(t.id, 'wh-a', 'A')
    inv.record(t.id, StockMovement('item-1', 'wh-a', Decimal('10'), 'in', 'GRN-1'))
    inv.record(t.id, StockMovement('item-2', 'wh-a', Decimal('5'), 'in', 'GRN-2'))
    return s, t, CommerceProductionService(s)


def test_create_draft_calculates_exact_total_and_is_tenant_scoped():
    s,t,c = setup()
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [
        OrderLineInput('item-1', Decimal('2'), Decimal('100.25')),
        OrderLineInput('item-2', Decimal('1.5'), Decimal('20')),
    ])
    assert o.total == Decimal('230.50') and o.status == 'draft'
    assert s.query(SalesOrderLine).filter_by(order_id=o.id).count() == 2


def test_confirm_atomically_reserves_all_lines_and_reduces_available():
    s,t,c = setup()
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('4'), Decimal('10'))])
    c.confirm(t.id, o.id)
    r = s.query(InventoryReservation).filter_by(tenant_id=t.id).one()
    assert r.status == 'active' and r.quantity == Decimal('4')
    from app.engines.inventory.production import InventoryProductionService
    assert InventoryProductionService(s).snapshot(t.id, 'item-1', 'wh-a').available == Decimal('6')


def test_confirm_rejects_when_combined_lines_exceed_available():
    s,t,c = setup()
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [
        OrderLineInput('item-1', Decimal('6'), Decimal('1')),
        OrderLineInput('item-1', Decimal('5'), Decimal('1')),
    ])
    with pytest.raises(CommerceError, match='insufficient'):
        c.confirm(t.id, o.id)
    assert s.get(SalesOrder, o.id).status == 'draft'
    assert s.query(InventoryReservation).count() == 0


def test_cancel_releases_reservations():
    s,t,c = setup()
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('4'), Decimal('10'))])
    c.confirm(t.id, o.id); c.cancel(t.id, o.id)
    assert s.get(SalesOrder, o.id).status == 'cancelled'
    assert s.query(InventoryReservation).one().status == 'released'


def test_fulfill_creates_authoritative_out_movements_and_closes_reservations():
    s,t,c = setup()
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [
        OrderLineInput('item-1', Decimal('4'), Decimal('10')),
        OrderLineInput('item-2', Decimal('2'), Decimal('5')),
    ])
    c.confirm(t.id, o.id); c.fulfill(t.id, o.id)
    assert s.get(SalesOrder, o.id).status == 'fulfilled'
    assert s.query(InventoryReservation).filter_by(status='active').count() == 0
    outs = s.query(InventoryMovementRecord).filter_by(tenant_id=t.id, direction='out').all()
    assert sum((Decimal(str(x.quantity)) for x in outs), Decimal('0')) == Decimal('6')


def test_fulfill_is_not_allowed_twice():
    s,t,c = setup()
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('2'), Decimal('10'))])
    c.confirm(t.id, o.id); c.fulfill(t.id, o.id)
    with pytest.raises(CommerceError, match='confirmed'):
        c.fulfill(t.id, o.id)


def test_cross_tenant_order_access_is_denied():
    s,t,c = setup(); t2 = IdentityService(s).create_tenant('Other')
    o = c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('1'), Decimal('10'))])
    with pytest.raises(CommerceError, match='not found'):
        c.confirm(t2.id, o.id)


def test_duplicate_order_reference_is_blocked_per_tenant():
    s,t,c = setup()
    c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('1'), Decimal('10'))])
    with pytest.raises(CommerceError, match='duplicate'):
        c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-2', Decimal('1'), Decimal('10'))])


def test_other_tenant_can_reuse_order_reference():
    s,t,c = setup(); t2 = IdentityService(s).create_tenant('Other')
    inv = InventoryProductionService(s); inv.create_item(t2.id, 'item-1', 'Other Item'); inv.create_warehouse(t2.id, 'wh-a', 'Other WH')
    c.create_draft(t.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('1'), Decimal('10'))])
    o2 = c.create_draft(t2.id, 'SO-1', 'wh-a', 'YER', [OrderLineInput('item-1', Decimal('1'), Decimal('10'))])
    assert o2.reference == 'SO-1'
