from uuid import uuid4
from app.ai.runtime import create_run, propose_action, approve_action, AIError
from app.hus.compiler import compile_spec, HUSCompileError
from app.core.models.ai_hus import AIToolDefinition, AIRun, AIAction
from app.core.models.core import Tenant, User, TenantMembership
from app.core.persistence import make_session_factory

import pytest

@pytest.fixture
def db():
    _, factory = make_session_factory(); return factory()

def seed(db, tenant_id=1):
    db.add(Tenant(id=tenant_id,name='T',status='active')); db.add(User(id='u1',email='u@example.com',active=True)); db.add(TenantMembership(user_id='u1',tenant_id=tenant_id,role='admin',active=True)); db.commit()

def test_hus_is_deterministic():
    spec={'spec_version':'1.0','organization':{'code':'shop','name':'Shop'},'domains':[{'code':'retail','name':'Retail','engine':'retail'}],'workflows':[{'code':'sale','trigger':'sale.created','steps':[{'code':'confirm','action':'commerce.confirm','requires_approval':False}]}]}
    a=compile_spec(spec); b=compile_spec(spec)
    assert a['contract_hash']==b['contract_hash']; assert a['stages']==['Boot','Parser','Validator','Resolver','Contract Injector','Generator']

def test_hus_rejects_unsupported_engine():
    spec={'spec_version':'1.0','organization':{'code':'x','name':'X'},'domains':[{'code':'x','engine':'evil'}]}
    try: compile_spec(spec); assert False
    except HUSCompileError as e: assert 'unsupported_engine' in str(e)

def test_ai_mutation_requires_approval(db):
    seed(db)
    db.add(AIToolDefinition(tenant_id=1,code='stock.adjust',name='Adjust',description='adjust',risk='mutation',input_schema={},enabled=True)); db.commit()
    run=create_run(db,1,'u1','test',{'x':1})
    action=propose_action(db,1,'u1',run.id,'stock.adjust',{'qty':1})
    assert action.status=='pending_approval'
    approve_action(db,1,'u1',action.id)
    assert db.get(AIAction,action.id).status=='approved'

def test_ai_cross_tenant_action_denied(db):
    seed(db,1); db.add(Tenant(id=2,name='T2',status='active')); db.commit()
    db.add(AIToolDefinition(tenant_id=1,code='read.x',name='Read',description='read',risk='read',input_schema={},enabled=True)); db.commit()
    run=create_run(db,1,'u1','test',{})
    try: propose_action(db,2,'u1',run.id,'read.x',{}); assert False
    except AIError: assert True

def test_ai_read_tool_executes_only_after_proposal(db):
    seed(db)
    db.add(AIToolDefinition(tenant_id=1,code='retail.overview',name='Retail Overview',description='read',risk='read',input_schema={},enabled=True)); db.commit()
    run=create_run(db,1,'u1','overview',{})
    action=propose_action(db,1,'u1',run.id,'retail.overview',{})
    from app.ai.runtime import execute_read_action
    out=execute_read_action(db,1,'u1',action.id)
    assert out.status=='completed' and out.result['products']==0

def test_ai_read_tool_unknown_handler_is_rejected(db):
    seed(db)
    db.add(AIToolDefinition(tenant_id=1,code='not.registered',name='x',description='read',risk='read',input_schema={},enabled=True)); db.commit()
    run=create_run(db,1,'u1','x',{})
    action=propose_action(db,1,'u1',run.id,'not.registered',{})
    from app.ai.runtime import execute_read_action
    with pytest.raises(ValueError): execute_read_action(db,1,'u1',action.id)
