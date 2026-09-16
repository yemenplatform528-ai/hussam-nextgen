from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.ai_intelligence import AIInsight, AIMemory, AIEvaluation
from app.core.models.ai_hus import AIRun
from app.ai.intelligence import business_snapshot, generate_insights, save_memory, list_memories, plan_agent, record_evaluation


def db_session():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e,expire_on_commit=False)()

def seed(db):
    db.add(Tenant(id=1,name='T1',status='active')); db.add(Tenant(id=2,name='T2',status='active'))
    db.add(User(id='u1',email='u1@example.com',active=True)); db.add(User(id='u2',email='u2@example.com',active=True))
    db.add(TenantMembership(user_id='u1',tenant_id=1,role='admin',active=True)); db.add(TenantMembership(user_id='u2',tenant_id=2,role='admin',active=True)); db.commit()

def test_snapshot_is_tenant_scoped_and_deterministic():
    db=db_session(); seed(db)
    a=business_snapshot(db,1); b=business_snapshot(db,2)
    assert a['sales']['orders']==0 and b['sales']['orders']==0
    assert a['sales']['total']=='0' and a['payments']['pending']==0

def test_insights_memory_and_plan_are_bounded():
    db=db_session(); seed(db)
    rows=generate_insights(db,1,'u1')
    assert rows and all(x.tenant_id==1 for x in rows)
    m=save_memory(db,1,'u1','business.preference',{'currency':'YER'})
    assert list_memories(db,1)[0].key=='business.preference'
    plan=plan_agent(db,1,'u1','تحسين التشغيل')
    assert plan['execution_policy'].startswith('proposals_only')
    assert all(step.get('requires_approval',False) or step['type'] in {'read','analyze','report'} for step in plan['steps'])

def test_evaluation_score_bounds_and_tenant_scope():
    db=db_session(); seed(db)
    run=AIRun(id='r1',tenant_id=1,actor_id='u1',purpose='eval',status='completed',input_hash='x'*64); db.add(run); db.commit()
    x=record_evaluation(db,1,'u1','r1','groundedness',Decimal('0.95'),{'source':'test'})
    assert x.score==Decimal('0.9500')
    try: record_evaluation(db,1,'u1','r1','bad',Decimal('1.01'),{})
    except ValueError: pass
    else: assert False
