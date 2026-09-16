from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService, InventoryProductionError
from app.core.contracts import StockMovement
from app.core.models.inventory import InventoryMovementRecord, InventoryReservation

def db():
    _, factory = make_session_factory(); return factory()

def setup():
    s=db(); t=IdentityService(s).create_tenant('Inventory Tenant'); inv=InventoryProductionService(s)
    inv.create_item(t.id,'item-1','Item 1','unit')
    inv.create_warehouse(t.id,'wh-a','A')
    inv.create_warehouse(t.id,'wh-b','B')
    return s,t,inv

def test_receipt_sale_and_derived_balance():
    s,t,inv=setup()
    inv.record(t.id,StockMovement('item-1','wh-a',Decimal('10'),'in','GRN-1'))
    assert inv.snapshot(t.id,'item-1','wh-a').on_hand == Decimal('10')
    inv.record(t.id,StockMovement('item-1','wh-a',Decimal('3'),'out','SALE-1'))
    snap=inv.snapshot(t.id,'item-1','wh-a')
    assert snap.on_hand == Decimal('7') and snap.available == Decimal('7')

def test_negative_stock_is_blocked():
    s,t,inv=setup()
    with pytest.raises(InventoryProductionError, match='insufficient'):
        inv.record(t.id,StockMovement('item-1','wh-a',Decimal('1'),'out','SALE-1'))

def test_transfer_moves_stock_atomically():
    s,t,inv=setup()
    inv.record(t.id,StockMovement('item-1','wh-a',Decimal('8'),'in','GRN-1'))
    inv.record(t.id,StockMovement('item-1','wh-a',Decimal('5'),'transfer','TR-1','wh-b'))
    assert inv.snapshot(t.id,'item-1','wh-a').on_hand == Decimal('3')
    assert inv.snapshot(t.id,'item-1','wh-b').on_hand == Decimal('5')
    assert s.query(InventoryMovementRecord).count() == 2

def test_reservation_reduces_available_and_release_restores_it():
    s,t,inv=setup(); inv.record(t.id,StockMovement('item-1','wh-a',Decimal('10'),'in','GRN-1'))
    r=inv.reserve(t.id,'item-1','wh-a',Decimal('6'),'RES-1')
    snap=inv.snapshot(t.id,'item-1','wh-a'); assert snap.reserved == Decimal('6') and snap.available == Decimal('4')
    inv.release(t.id,r.id)
    assert inv.snapshot(t.id,'item-1','wh-a').available == Decimal('10')

def test_reservation_fulfillment_is_single_transaction():
    s,t,inv=setup(); inv.record(t.id,StockMovement('item-1','wh-a',Decimal('10'),'in','GRN-1'))
    r=inv.reserve(t.id,'item-1','wh-a',Decimal('4'),'RES-1')
    inv.fulfill(t.id,r.id,'SALE-1')
    assert s.get(InventoryReservation,r.id).status == 'fulfilled'
    snap=inv.snapshot(t.id,'item-1','wh-a'); assert snap.on_hand == Decimal('6') and snap.reserved == Decimal('0')

def test_fulfillment_fails_if_reserved_physical_stock_disappeared():
    s,t,inv=setup(); inv.record(t.id,StockMovement('item-1','wh-a',Decimal('5'),'in','GRN-1'))
    r=inv.reserve(t.id,'item-1','wh-a',Decimal('4'),'RES-1')
    # Reservation protects available stock, but an administrative negative-stock override could consume it.
    from app.core.models.inventory import Warehouse
    wh=s.get(Warehouse, {'id':'wh-a','tenant_id':t.id}); wh.allow_negative_stock=True; s.commit()
    inv.record(t.id,StockMovement('item-1','wh-a',Decimal('5'),'out','ADJ-1'))
    with pytest.raises(InventoryProductionError, match='physically available'):
        inv.fulfill(t.id,r.id,'SALE-1')

def test_tenant_isolation_and_duplicate_references():
    s,t1,inv=setup(); t2=IdentityService(s).create_tenant('Other')
    inv.record(t1.id,StockMovement('item-1','wh-a',Decimal('5'),'in','REF-1'))
    with pytest.raises(InventoryProductionError, match='item not found'):
        inv.snapshot(t2.id,'item-1','wh-a')
    with pytest.raises(InventoryProductionError, match='duplicate'):
        inv.record(t1.id,StockMovement('item-1','wh-a',Decimal('1'),'in','REF-1'))

def test_outbox_event_is_written_for_inventory_change():
    from app.core.models.governance import OutboxEvent
    s,t,inv=setup(); inv.record(t.id,StockMovement('item-1','wh-a',Decimal('2'),'in','GRN-1'))
    e=s.query(OutboxEvent).filter_by(tenant_id=t.id,event_type='inventory.movement.recorded').one()
    assert e.payload['reference']=='GRN-1' and e.published is False

def test_same_item_and_warehouse_codes_can_exist_in_different_tenants():
    s,t1,inv1=setup(); t2=IdentityService(s).create_tenant('Tenant 2'); inv2=InventoryProductionService(s)
    inv2.create_item(t2.id,'item-1','Same code in tenant 2')
    inv2.create_warehouse(t2.id,'wh-a','Same warehouse code in tenant 2')
    inv2.record(t2.id,StockMovement('item-1','wh-a',Decimal('2'),'in','REF-2'))
    assert inv1.snapshot(t1.id,'item-1','wh-a').on_hand == Decimal('0')
    assert inv2.snapshot(t2.id,'item-1','wh-a').on_hand == Decimal('2')


def test_expired_reservation_no_longer_reduces_available_stock():
    from datetime import datetime, timedelta, timezone
    s,t,inv=setup(); inv.record(t.id,StockMovement('item-1','wh-a',Decimal('10'),'in','GRN-EXP'))
    r=inv.reserve(t.id,'item-1','wh-a',Decimal('6'),'RES-EXP')
    r.expires_at=datetime.now(timezone.utc)-timedelta(minutes=1); s.commit()
    assert inv.snapshot(t.id,'item-1','wh-a').reserved == Decimal('0')
    assert inv.snapshot(t.id,'item-1','wh-a').available == Decimal('10')
    with pytest.raises(InventoryProductionError, match='expired'):
        inv.fulfill(t.id,r.id,'SALE-EXP')
    assert s.get(InventoryReservation,r.id).status == 'expired'
