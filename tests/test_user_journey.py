import os, time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.api.main import app
from app.api import dependencies
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.security.jwt import encode_hs256


def setup_client():
    engine=create_engine('sqlite+pysqlite:///:memory:',future=True,connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Factory=sessionmaker(bind=engine,expire_on_commit=False,autoflush=False)
    with Factory() as db:
        db.add_all([
            Tenant(id=1,name='Journey Tenant',status='active'),
            Tenant(id=2,name='Other Tenant',status='active'),
            User(id='u1',email='u@example.com',active=True),
            TenantMembership(user_id='u1',tenant_id=1,role='owner',active=True),
        ])
        db.commit()
    def override_session():
        db=Factory()
        try: yield db
        finally: db.close()
    app.dependency_overrides[dependencies.get_session]=override_session
    os.environ['JWT_SECRET']='x'*32
    token=encode_hs256({'sub':'u1','tenant_id':1,'exp':int(time.time())+3600},os.environ['JWT_SECRET'])
    return TestClient(app), token


def teardown(): app.dependency_overrides.clear()


def test_user_journey_session_and_dashboard_are_authenticated_and_tenant_scoped():
    client, token=setup_client()
    try:
        h={'Authorization':f'Bearer {token}'}
        assert client.get('/api/v1/session',headers=h).json()['tenant_id']==1
        r=client.get('/api/v1/dashboard/summary',headers=h)
        assert r.status_code==200
        data=r.json()
        assert data['tenant_id']==1
        assert data['counts']['items']==0
        assert data['status']['sales_orders']=={}
        assert client.get('/api/v1/dashboard/summary').status_code==401
    finally: teardown()


def test_platform_version_is_1_18():
    client, token=setup_client()
    try:
        assert client.get('/health').json()['version']=='1.0.0'
        assert client.get('/api/v1/platform/manifest').json()['version']=='1.0.0'
    finally: teardown()
