from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.commerce import CommerceProductionService, OrderLineInput
from app.engines.logistics import LogisticsProductionService
from app.engines.carriers import CarrierLifecycleService, CarrierError
from app.core.contracts import StockMovement
from app.core.models.logistics import CarrierEvent, Shipment

def setup():
    _, factory=make_session_factory(); s=factory(); t=IdentityService(s).create_tenant('Carrier Tenant')
    inv=InventoryProductionService(s); inv.create_item(t.id,'item-1','Item 1'); inv.create_warehouse(t.id,'wh-a','A'); inv.record(t.id,StockMovement('item-1','wh-a',10,'in','GRN-1'))
    c=CommerceProductionService(s); o=c.create_draft(t.id,'SO-1','wh-a','YER',[OrderLineInput('item-1',1,100)]); c.confirm(t.id,o.id); c.fulfill(t.id,o.id)
    sh=LogisticsProductionService(s).create_shipment(t.id,order_id=o.id,reference='SHP-1',origin_warehouse_id='wh-a',destination='Aden',carrier='acme',currency='YER',tracking_number='TRK-1')
    return s,t,sh,CarrierLifecycleService(s)

def test_signed_carrier_event_is_verified_and_idempotent():
    s,t,sh,c=setup(); c.register(t.id,'acme','Acme Carrier'); payload={'status':'picked_up','shipment':'SHP-1'}; sig=c.sign(payload,'secret-123')
    x=c.ingest_event(t.id,'acme',external_event_id='evt-1',shipment_reference='SHP-1',event_type='picked_up',payload=payload,signature=sig,secret='secret-123')
    y=c.ingest_event(t.id,'acme',external_event_id='evt-1',shipment_reference='SHP-1',event_type='picked_up',payload=payload,signature=sig,secret='secret-123')
    assert x.id==y.id and s.get(Shipment,sh.id).status=='picked_up' and s.query(CarrierEvent).count()==1

def test_invalid_signature_and_payload_replay_are_rejected():
    s,t,sh,c=setup(); c.register(t.id,'acme','Acme Carrier'); payload={'status':'picked_up'}; sig=c.sign(payload,'secret-123')
    with pytest.raises(CarrierError,match='signature'):
        c.ingest_event(t.id,'acme',external_event_id='evt-1',shipment_reference='SHP-1',event_type='picked_up',payload=payload,signature='bad',secret='secret-123')
    c.ingest_event(t.id,'acme',external_event_id='evt-1',shipment_reference='SHP-1',event_type='picked_up',payload=payload,signature=sig,secret='secret-123')
    with pytest.raises(CarrierError,match='payload mismatch'):
        c.ingest_event(t.id,'acme',external_event_id='evt-1',shipment_reference='SHP-1',event_type='picked_up',payload={'status':'tampered'},signature=c.sign({'status':'tampered'},'secret-123'),secret='secret-123')

def test_carrier_event_respects_tenant_and_lifecycle():
    s,t,sh,c=setup(); c.register(t.id,'acme','Acme Carrier'); other=IdentityService(s).create_tenant('Other')
    payload={'status':'delivered'}; sig=c.sign(payload,'secret-123')
    with pytest.raises(CarrierError,match='carrier integration'):
        c.ingest_event(other.id,'acme',external_event_id='evt-x',shipment_reference='SHP-1',event_type='delivered',payload=payload,signature=sig,secret='secret-123')
    with pytest.raises(CarrierError,match='invalid shipment transition'):
        c.ingest_event(t.id,'acme',external_event_id='evt-2',shipment_reference='SHP-1',event_type='delivered',payload=payload,signature=sig,secret='secret-123')
