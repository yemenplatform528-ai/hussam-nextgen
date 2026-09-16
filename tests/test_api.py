import os, time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.api.main import app
from app.api import dependencies
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.security.jwt import encode_hs256


def setup_client():
    engine=create_engine("sqlite+pysqlite:///:memory:",future=True,connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Factory=sessionmaker(bind=engine,expire_on_commit=False,autoflush=False)
    with Factory() as db:
        db.add_all([Tenant(id=1,name="Demo",status="active"),User(id="u1",email="u@example.com",active=True),TenantMembership(user_id="u1",tenant_id=1,role="owner",active=True)])
        db.commit()
    def override_session():
        db=Factory()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[dependencies.get_session]=override_session
    os.environ["JWT_SECRET"]="x"*32
    token=encode_hs256({"sub":"u1","tenant_id":1,"exp":int(time.time())+3600},os.environ["JWT_SECRET"])
    return TestClient(app), Factory, token

def teardown():
    app.dependency_overrides.clear()

def test_api_health_and_auth_boundary():
    client,_,token=setup_client()
    try:
        assert client.get("/health").status_code==200
        assert client.get("/api/v1/inventory/stock/x/y").status_code==401
        assert client.get("/api/v1/platform/manifest").json()["version"]=="1.0.0"
        assert client.get("/api/v1/inventory/stock/x/y",headers={"Authorization":f"Bearer {token}"}).status_code==400
    finally: teardown()

def test_inventory_api_uses_authenticated_tenant():
    client,Factory,token=setup_client()
    try:
        h={"Authorization":f"Bearer {token}"}
        assert client.post("/api/v1/inventory/items",json={"id":"i1","name":"Item"},headers=h).status_code==201
        assert client.post("/api/v1/inventory/warehouses",json={"id":"w1","name":"Main"},headers=h).status_code==201
        r=client.post("/api/v1/inventory/movements",json={"item_id":"i1","warehouse_id":"w1","quantity":"10","direction":"in","reference":"m1"},headers=h)
        assert r.status_code==201
        assert client.get("/api/v1/inventory/stock/i1/w1",headers=h).json()["available"]=="10.0000"
    finally: teardown()

def test_retail_api_is_authenticated_and_tenant_scoped():
    client, _, token = setup_client()
    try:
        assert client.get('/api/v1/retail/overview').status_code == 401
        h = {'Authorization': f'Bearer {token}'}
        r = client.post('/api/v1/retail/products', headers=h, json={'item_id':'r1','name':'Rice','sku':'R-1','currency':'YER','unit_price':'1000'})
        assert r.status_code == 201
        r = client.post('/api/v1/retail/customers', headers=h, json={'id':'c1','name':'Customer'})
        assert r.status_code == 201
        assert client.get('/api/v1/retail/products', headers=h).json()['items'][0]['sku'] == 'R-1'
        assert client.get('/api/v1/retail/overview', headers=h).json()['products'] == 1
    finally:
        teardown()

def test_ai_and_hus_api_boundaries():
    client, _, token = setup_client()
    try:
        assert client.get('/api/v1/ai/tools').status_code == 401
        h={'Authorization':f'Bearer {token}'}
        r=client.post('/api/v1/hus/compile',headers=h,json={'spec':{
            'spec_version':'1.0','organization':{'code':'demo','name':'Demo'},
            'domains':[{'code':'retail','name':'Retail','engine':'retail'}],
            'workflows':[{'code':'sale','trigger':'sale.created','steps':[{'code':'confirm','action':'commerce.confirm'}]}]
        }})
        assert r.status_code == 200
        assert r.json()['status'] == 'compiled'
        assert r.json()['stages'][-1] == 'Generator'
        run=client.post('/api/v1/ai/runs',headers=h,json={'purpose':'inventory analysis','payload':{'warehouse':'w1'}})
        assert run.status_code == 201
        client.post('/api/v1/ai/tools',headers=h,json={'code':'inventory.read','name':'Inventory Read','description':'Read inventory','risk':'read','input_schema':{}})
        action=client.post('/api/v1/ai/actions',headers=h,json={'run_id':run.json()['id'],'tool_code':'inventory.read','arguments':{}})
        assert action.status_code == 201 and action.json()['status']=='approved'
    finally: teardown()
