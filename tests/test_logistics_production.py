from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.commerce import CommerceProductionService, OrderLineInput
from app.engines.logistics import LogisticsProductionService, LogisticsError
from app.core.contracts import StockMovement
from app.core.models.logistics import Shipment, ShipmentEvent, ShipmentCollection


def setup():
    _, factory = make_session_factory(); s = factory(); t = IdentityService(s).create_tenant('Logistics Tenant')
    inv = InventoryProductionService(s); inv.create_item(t.id,'item-1','Item 1'); inv.create_warehouse(t.id,'wh-a','A')
    inv.record(t.id, StockMovement('item-1','wh-a',10,'in','GRN-1'))
    c = CommerceProductionService(s); o = c.create_draft(t.id,'SO-1','wh-a','YER',[OrderLineInput('item-1',2,100)])
    c.confirm(t.id,o.id); c.fulfill(t.id,o.id)
    return s,t,o,LogisticsProductionService(s)


def test_create_shipment_requires_fulfilled_order_and_matches_origin():
    s,t,o,l = setup(); x=l.create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER',cod_amount=Decimal('200'))
    assert x.status=='ready' and x.cod_amount==Decimal('200')
    with pytest.raises(LogisticsError,match='origin'):
        l.create_shipment(t.id,order_id=o.id,reference='SHP-2',origin_warehouse_id='other',destination='Aden',carrier='local',currency='YER')


def test_tracking_number_is_unique_and_immutable():
    s,t,o,l=setup(); x=l.create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER')
    l.assign_tracking(t.id,x.id,'TRK-1')
    with pytest.raises(LogisticsError,match='cannot be changed'):
        l.assign_tracking(t.id,x.id,'TRK-2')
    with pytest.raises(LogisticsError,match='duplicate'):
        l.create_shipment(t.id,order_id=o.id,reference='SHP-2',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER',tracking_number='TRK-1')


def test_lifecycle_is_ordered_and_tracking_required():
    s,t,o,l=setup(); x=l.create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER')
    with pytest.raises(LogisticsError,match='tracking'):
        l.transition(t.id,x.id,'picked_up',event_id='e1')
    l.assign_tracking(t.id,x.id,'TRK-1')
    l.transition(t.id,x.id,'picked_up',event_id='e1',location='Warehouse')
    l.transition(t.id,x.id,'in_transit',event_id='e2',location='Road')
    l.transition(t.id,x.id,'out_for_delivery',event_id='e3',location='District')
    l.transition(t.id,x.id,'delivered',event_id='e4',location='Customer')
    assert s.get(Shipment,x.id).status=='delivered' and s.query(ShipmentEvent).filter_by(shipment_id=x.id).count()==4


def test_tracking_event_is_idempotent():
    s,t,o,l=setup(); x=l.create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER',tracking_number='TRK-1')
    a=l.transition(t.id,x.id,'picked_up',event_id='evt-1'); b=l.transition(t.id,x.id,'picked_up',event_id='evt-1')
    assert a.id==b.id and s.query(ShipmentEvent).count()==1


def test_invalid_backward_transition_and_cross_tenant_access_denied():
    s,t,o,l=setup(); x=l.create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER',tracking_number='TRK-1')
    t2=IdentityService(s).create_tenant('Other')
    with pytest.raises(LogisticsError,match='not found'):
        l.transition(t2.id,x.id,'picked_up',event_id='x')
    l.transition(t.id,x.id,'picked_up',event_id='e1')
    with pytest.raises(LogisticsError,match='invalid shipment transition'):
        l.transition(t.id,x.id,'ready',event_id='e2')


def test_cod_requires_delivery_exact_amount_currency_and_only_once():
    s,t,o,l=setup(); x=l.create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER',cod_amount=200,tracking_number='TRK-1')
    l.transition(t.id,x.id,'picked_up',event_id='e1'); l.transition(t.id,x.id,'in_transit',event_id='e2'); l.transition(t.id,x.id,'out_for_delivery',event_id='e3'); l.transition(t.id,x.id,'delivered',event_id='e4')
    with pytest.raises(LogisticsError,match='match COD'):
        l.create_cod_collection(t.id,x.id,reference='COL-1',amount=199,currency='YER')
    with pytest.raises(LogisticsError,match='match COD'):
        l.create_cod_collection(t.id,x.id,reference='COL-1',amount=200,currency='SAR')
    c=l.create_cod_collection(t.id,x.id,reference='COL-1',amount=200,currency='YER')
    assert c.status=='collected' and s.query(ShipmentCollection).count()==1
    with pytest.raises(LogisticsError,match='already exists'):
        l.create_cod_collection(t.id,x.id,reference='COL-2',amount=200,currency='YER')


def test_cod_amount_cannot_exceed_order_total():
    s,t,o,l=setup()
    with pytest.raises(LogisticsError,match='exceed'):
        l.create_shipment(t.id,order_id=o.id,reference='SHP-X',origin_warehouse_id='wh-a',destination='Aden',carrier='local',currency='YER',cod_amount=201)
