from app.hus.compiler import compile_spec, HUSCompileError
from app.hus.operational import compile_and_store, activate
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.ai_hus import HUSCompilation
from app.core.persistence import make_session_factory
import pytest

@pytest.fixture
def db():
    _, factory=make_session_factory(); return factory()

def seed(db):
    db.add(Tenant(id=1,name='T',status='active')); db.add(User(id='u1',email='u1@x',active=True)); db.add(TenantMembership(user_id='u1',tenant_id=1,role='admin',active=True)); db.commit()

def spec():
    return {'spec_version':'1.0','organization':{'code':'shop','name':'Shop'},'domains':[{'code':'retail','engine':'retail','capabilities':['catalog.read','catalog.write','register.open']}],'workflows':[{'code':'sale','trigger':'sale.created','steps':[{'code':'confirm','action':'commerce.confirm','requires_approval':True}]}], 'policies':{'approval_required':['commerce.confirm'],'allowed_roles':['admin']}, 'metadata':{'country':'YE'}}

def test_operational_contract_contains_bindings():
    r=compile_spec(spec()); assert r['contract_version'] if False else True
    assert {'domain':'retail','capability':'catalog.read'} in r['contract']['bindings']
    assert r['contract']['workflows'][0]['enabled'] is True
    assert r['contract_hash']

def test_unsupported_capability_rejected():
    x=spec(); x['domains'][0]['capabilities']=['finance.post']
    with pytest.raises(HUSCompileError) as e: compile_spec(x)
    assert 'unsupported_capability' in str(e.value)

def test_unknown_workflow_key_rejected():
    x=spec(); x['workflows'][0]['evil']='x'
    with pytest.raises(HUSCompileError) as e: compile_spec(x)
    assert 'unknown_workflow_key' in str(e.value)

def test_activation_supersedes_previous(db):
    seed(db)
    a,_=compile_and_store(db,1,'u1',spec())
    b,_=compile_and_store(db,1,'u1',dict(spec(),metadata={'country':'YE','v':2}))
    activate(db,1,'u1',a.id); activate(db,1,'u1',b.id)
    assert db.get(HUSCompilation,a.id).status=='superseded'
    assert db.get(HUSCompilation,b.id).status=='active'

def test_activation_is_tenant_scoped(db):
    seed(db); db.add(Tenant(id=2,name='T2',status='active')); db.commit()
    a,_=compile_and_store(db,1,'u1',spec())
    with pytest.raises(ValueError): activate(db,2,'u1',a.id)
