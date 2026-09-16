from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from app.core.persistence import Base
from app.core.models.ai_hus import HUSCompilation
from app.hus.runtime import SovereignRuntime, HUSRuntimeError
from app.hus.bindings import build_production_bindings


def db():
    e=create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e, expire_on_commit=False)()


def active(db, action, risk='read', idem=False):
    x=HUSCompilation(id='c1', tenant_id=1, actor_id='owner', spec_version='1.0', source_hash='s'*64, contract_hash='p'*64, status='active', contract={
        'execution_plan': {'workflows':[{'code':'w','steps':[{'id':'w.step','action':{'engine':action.split('.')[0],'capability':action.split('.',1)[1]},'risk':risk,'idempotency_required':idem}]}]}
    })
    db.add(x); db.commit()


def test_real_read_binding_is_tenant_scoped():
    s=db(); active(s,'commerce.sales.read'); r=SovereignRuntime(s)
    for a,h in build_production_bindings().items():
        if a != 'commerce.sales.create': r.register_read_handler(a,h)
    out=r.execute_step(1,'u','c1','w.step',{})
    assert out.status=='completed'
    assert out.output['result']['orders']==0


def test_finance_and_payments_bindings_are_registered_reads():
    s=db(); active(s,'finance.finance.read'); r=SovereignRuntime(s)
    r.register_read_handler('finance.finance.read', build_production_bindings()['finance.finance.read'])
    assert r.execute_step(1,'u','c1','w.step',{}).output['result']['journals']==0


def test_mutation_binding_calls_domain_service_with_real_invariants():
    s=db(); active(s,'commerce.sales.create',risk='mutation',idem=True); r=SovereignRuntime(s)
    r.register_mutation_handler('commerce.sales.create', build_production_bindings()['commerce.sales.create'])
    with pytest.raises(HUSRuntimeError, match='failed'):
        r.execute_step(1,'u','c1','w.step',{'reference':'x','currency':'YER','lines':[]},approved=True,approval_ref='ap',idempotency_key='k')


def test_production_mutation_requires_verifiable_approval():
    s=db(); active(s,'commerce.sales.create',risk='mutation',idem=True); r=SovereignRuntime(s)
    r.register_mutation_handler('commerce.sales.create', build_production_bindings()['commerce.sales.create'])
    r.configure_approval_verifier(lambda db,ctx: False)
    with pytest.raises(HUSRuntimeError, match='approval evidence'):
        r.execute_step(1,'u','c1','w.step',{'reference':'x','currency':'YER','lines':[]},approved=True,approval_ref='ap',idempotency_key='k')
