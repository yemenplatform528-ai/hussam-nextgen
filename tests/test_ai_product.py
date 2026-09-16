from decimal import Decimal
import pytest
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.ai_foundation import AIProviderConfig
from app.core.models.ai_product import AIReleaseGate
from app.ai.foundation import register_provider
from app.ai.product import record_provider_health, register_evaluation_suite, record_evaluation_result, build_release_gate, control_change, security_release_snapshot
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def db_session():
    e = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e, expire_on_commit=False)()


def seed(db):
    db.add_all([Tenant(id=1,name='T1',status='active'), Tenant(id=2,name='T2',status='active'),
                User(id='u1',email='u1@example.com',active=True), User(id='u2',email='u2@example.com',active=True),
                TenantMembership(user_id='u1',tenant_id=1,role='admin',active=True), TenantMembership(user_id='u2',tenant_id=2,role='admin',active=True)])
    db.commit()


def test_provider_health_is_tenant_scoped_and_rejects_unknown_provider():
    db=db_session(); seed(db)
    register_provider(db,1,code='p1',provider_kind='compatible',enabled=True)
    row=record_provider_health(db,1,'p1',status='healthy',latency_ms=20)
    assert row.status=='healthy'
    with pytest.raises(ValueError): record_provider_health(db,2,'p1',status='healthy')


def test_evaluation_threshold_and_release_gate_block_then_ready():
    db=db_session(); seed(db)
    register_evaluation_suite(db,1,'ai04-security','1.0',['memory_isolation','tool_authorization'],Decimal('0.90'))
    record_evaluation_result(db,1,'ai04-security','run-a','memory_isolation',Decimal('1.0'))
    record_evaluation_result(db,1,'ai04-security','run-a','tool_authorization',Decimal('0.80'))
    gate=build_release_gate(db,1,'ai-product-1',['memory_isolation','tool_authorization'])
    assert gate.status=='blocked' and 'tool_authorization' in gate.blocked_reason
    record_evaluation_result(db,1,'ai04-security','run-b','tool_authorization',Decimal('1.0'))
    gate=build_release_gate(db,1,'ai-product-1',['memory_isolation','tool_authorization'])
    assert gate.status=='ready' and len(gate.passed_checks)==2


def test_control_center_cannot_store_secrets_or_database_state():
    db=db_session(); seed(db)
    row=control_change(db,1,'u1',resource_type='model_route',resource_code='commerce-default',action='disable',before_state={'enabled':True},after_state={'enabled':False})
    assert row.status=='applied'
    with pytest.raises(ValueError): control_change(db,1,'u1',resource_type='provider',resource_code='p',action='update',before_state={},after_state={'api_key':'secret'})
    with pytest.raises(ValueError): control_change(db,1,'u1',resource_type='provider',resource_code='p',action='update',before_state={},after_state={'database_url':'sqlite://'})


def test_release_snapshot_is_tenant_scoped():
    db=db_session(); seed(db)
    register_provider(db,1,code='p1',provider_kind='compatible',enabled=True)
    register_provider(db,2,code='p2',provider_kind='compatible',enabled=True)
    snap=security_release_snapshot(db,1)
    assert snap['tenant_id']==1 and snap['providers']['count']==1 and snap['providers']['enabled']==1
