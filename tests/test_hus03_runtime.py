from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from app.core.persistence import Base
from app.core.models.ai_hus import HUSCompilation
from app.hus.runtime import SovereignRuntime, HUSRuntimeError


def db():
    e=create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e, expire_on_commit=False)()


def active(db, tenant=1):
    x=HUSCompilation(id='c1', tenant_id=tenant, actor_id='owner', spec_version='1.0', source_hash='s'*64, contract_hash='p'*64, status='active', contract={
        'execution_plan': {'workflows':[{'code':'w','steps':[{'id':'w.read','action':{'engine':'marketplace','capability':'marketplace.read'},'risk':'read','idempotency_required':False},{'id':'w.write','action':{'engine':'commerce','capability':'sales.create'},'risk':'mutation','idempotency_required':True}]}]}
    })
    db.add(x); db.commit(); return x


def test_runtime_rejects_cross_tenant_compilation():
    s=db(); active(s, 7); r=SovereignRuntime(s)
    with pytest.raises(HUSRuntimeError): r.authorize(8,'u','c1','w.read')


def test_read_handler_executes_and_records_provenance():
    s=db(); active(s); r=SovereignRuntime(s)
    r.register_read_handler('marketplace.marketplace.read', lambda db,ctx,args: {'ok': True, 'tenant': ctx.tenant_id})
    out=r.execute_step(1,'u','c1','w.read',{}, idempotency_key='read-1')
    assert out.status=='completed'
    assert out.output['provenance']['plan_hash']=='p'*64
    replay=r.execute_step(1,'u','u' if False else 'c1','w.read',{}, idempotency_key='read-1')
    assert replay.replayed is True and replay.execution_id==out.execution_id


def test_mutation_requires_approval_and_idempotency():
    s=db(); active(s); r=SovereignRuntime(s)
    with pytest.raises(HUSRuntimeError, match='approval'):
        r.execute_step(1,'u','c1','w.write',{}, approved=False, idempotency_key='m1', approval_ref='ap1')
    with pytest.raises(HUSRuntimeError, match='idempotency'):
        r.execute_step(1,'u','c1','w.write',{}, approved=True, approval_ref='ap1')


def test_registered_capability_without_handler_fails_closed():
    s=db(); active(s); r=SovereignRuntime(s)
    with pytest.raises(HUSRuntimeError, match='handler'):
        r.execute_step(1,'u','c1','w.read',{})
