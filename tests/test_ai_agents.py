from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.ai.agents import AgentTask, orchestrate, complete_delegation
from app.core.models.ai_agents import AIAgentRun, AIAgentDelegation


def db_session():
    e = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e, expire_on_commit=False)()


def seed(db):
    db.add_all([Tenant(id=1,name='T1',status='active'), Tenant(id=2,name='T2',status='active'),
                User(id='u1',email='u1@example.com',active=True), User(id='u2',email='u2@example.com',active=True),
                TenantMembership(user_id='u1',tenant_id=1,role='admin',active=True),
                TenantMembership(user_id='u2',tenant_id=2,role='admin',active=True)])
    db.commit()


def test_orchestrator_selects_bounded_specialists_and_never_executes_mutation():
    db=db_session(); seed(db)
    out=orchestrate(db,1,'u1',AgentTask(goal='review seller listings and marketplace orders'))
    assert out['status']=='delegated'
    assert 'seller_operations_assistant' in out['selected_agents']
    assert 'marketplace_operations_assistant' in out['selected_agents']
    assert len(out['delegations']) <= 4
    assert all(x['depth']==1 for x in out['delegations'])
    assert all(x['status']=='planned' for x in out['delegations'])


def test_agent_run_is_tenant_isolated():
    db=db_session(); seed(db)
    out=orchestrate(db,1,'u1',AgentTask(goal='finance and risk review'))
    assert db.scalar(__import__('sqlalchemy').select(AIAgentRun).where(AIAgentRun.id==out['run_id'],AIAgentRun.tenant_id==2)) is None
    try:
        complete_delegation(db,2,out['delegations'][0]['id'],{'x':1})
        assert False
    except ValueError as exc:
        assert 'tenant' in str(exc)


def test_depth_budget_is_hard_bounded():
    db=db_session(); seed(db)
    try:
        orchestrate(db,1,'u1',AgentTask(goal='anything',max_depth=3))
        assert False
    except ValueError as exc:
        assert 'depth' in str(exc)


def test_delegation_completion_does_not_change_agent_authority():
    db=db_session(); seed(db)
    out=orchestrate(db,1,'u1',AgentTask(goal='seller review'))
    d=complete_delegation(db,1,out['delegations'][0]['id'],{'recommendation':'review'},status='completed')
    assert d.status=='completed'
    assert d.allowed_scopes
    assert d.result['recommendation']=='review'
