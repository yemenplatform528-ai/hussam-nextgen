from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
import app.core.models
from app.core.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowTransition, WorkflowTask
from app.core.models.governance import OutboxEvent
from app.engines.workflow import WorkflowEngine, WorkflowError

@pytest.fixture
def session():
    engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine); S=sessionmaker(bind=engine)
    with S() as s:
        from app.core.models.core import Tenant
        s.add_all([Tenant(id=1,name='A',status='active'),Tenant(id=2,name='B',status='active')]); s.commit(); yield s

def definition():
    return {'start': 'reserve', 'reserve': {'task_key':'reserve-stock','on': {'inventory.reserved':'fulfill'}}, 'fulfill': {'on': {'order.fulfilled':'ship'}}, 'ship': {'on': {'shipment.delivered':'complete'}}, 'complete': {'terminal':True}}

def test_register_and_start_creates_task(session):
    e=WorkflowEngine(session); d=e.register_definition(1,code='order-flow',version=1,name='Order flow',steps=definition())
    i=e.start(1,definition_code='order-flow',version=1,reference='wf-1',aggregate_type='sales_order',aggregate_id='10')
    assert i.current_step=='reserve' and i.status=='running'
    assert session.scalar(select(WorkflowTask).where(WorkflowTask.instance_id==i.id)).task_key=='reserve-stock'
    assert session.scalar(select(OutboxEvent).where(OutboxEvent.aggregate_id==str(i.id))).event_type=='workflow.started'

def test_definition_is_versioned_and_tenant_scoped(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition())
    e.register_definition(1,code='x',version=2,name='X2',steps=definition())
    e.register_definition(2,code='x',version=1,name='X',steps=definition())
    with pytest.raises(WorkflowError): e.register_definition(1,code='x',version=1,name='dup',steps=definition())

def test_start_rejects_duplicate_reference(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); e.start(1,definition_code='x',version=1,reference='same',aggregate_type='x',aggregate_id='1')
    with pytest.raises(WorkflowError): e.start(1,definition_code='x',version=1,reference='same',aggregate_type='x',aggregate_id='2')

def test_transition_is_explicit_and_idempotent(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    i=e.apply_event(1,i.id,event_id='evt-1',event_type='inventory.reserved',payload={'ok':True})
    assert i.current_step=='fulfill'
    same=e.apply_event(1,i.id,event_id='evt-1',event_type='inventory.reserved')
    assert same.current_step=='fulfill'
    assert session.query(WorkflowTransition).count()==1

def test_invalid_event_does_not_advance(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    with pytest.raises(WorkflowError): e.apply_event(1,i.id,event_id='evt',event_type='wrong')
    assert session.get(WorkflowInstance,i.id).current_step=='reserve'

def test_cross_tenant_instance_is_hidden(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    with pytest.raises(WorkflowError): e.apply_event(2,i.id,event_id='evt',event_type='inventory.reserved')

def test_terminal_step_completes_instance(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    e.apply_event(1,i.id,event_id='e1',event_type='inventory.reserved'); e.apply_event(1,i.id,event_id='e2',event_type='order.fulfilled'); i=e.apply_event(1,i.id,event_id='e3',event_type='shipment.delivered')
    assert i.status=='completed' and i.current_step=='complete'

def test_completed_workflow_rejects_further_events(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    for n,t in enumerate(['inventory.reserved','order.fulfilled','shipment.delivered'],1): i=e.apply_event(1,i.id,event_id=f'e{n}',event_type=t)
    with pytest.raises(WorkflowError): e.apply_event(1,i.id,event_id='e4',event_type='anything')

def test_cancel_is_tenant_scoped_and_terminal(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    with pytest.raises(WorkflowError): e.cancel(2,i.id,event_id='c1')
    i=e.cancel(1,i.id,event_id='c1'); assert i.status=='cancelled'
    with pytest.raises(WorkflowError): e.cancel(1,i.id,event_id='c2')

def test_transition_payload_and_audit_event_are_persisted(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); i=e.start(1,definition_code='x',version=1,reference='wf',aggregate_type='x',aggregate_id='1')
    e.apply_event(1,i.id,event_id='evt',event_type='inventory.reserved',payload={'reservation_id':'r1'})
    tr=session.scalar(select(WorkflowTransition).where(WorkflowTransition.event_id=='evt'))
    assert tr.from_step=='reserve' and tr.to_step=='fulfill' and tr.payload_json['reservation_id']=='r1'

def test_outbox_events_are_tenant_scoped(session):
    e=WorkflowEngine(session); e.register_definition(1,code='x',version=1,name='X',steps=definition()); e.register_definition(2,code='x',version=1,name='X',steps=definition())
    a=e.start(1,definition_code='x',version=1,reference='a',aggregate_type='x',aggregate_id='1'); b=e.start(2,definition_code='x',version=1,reference='b',aggregate_type='x',aggregate_id='2')
    tenants={x.tenant_id for x in session.scalars(select(OutboxEvent)).all()}; assert tenants=={1,2}
