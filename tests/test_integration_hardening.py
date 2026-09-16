import os
import time
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.api import dependencies
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.finance import FiscalPeriod
from app.core.security.jwt import encode_hs256


def setup_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with Factory() as db:
        db.add_all([
            Tenant(id=1, name="Tenant One", status="active"),
            Tenant(id=2, name="Tenant Two", status="active"),
            User(id="u1", email="one@example.com", active=True),
            User(id="u2", email="two@example.com", active=True),
            TenantMembership(user_id="u1", tenant_id=1, role="owner", active=True),
            TenantMembership(user_id="u2", tenant_id=2, role="owner", active=True),
            FiscalPeriod(tenant_id=1, name="2026", starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31), closed=False),
            FiscalPeriod(tenant_id=2, name="2026", starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31), closed=False),
        ])
        db.commit()

    def override_session():
        db = Factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[dependencies.get_session] = override_session
    os.environ["JWT_SECRET"] = "x" * 32
    def token(user, tenant):
        return encode_hs256(
            {"sub": user, "tenant_id": tenant, "exp": int(time.time()) + 3600},
            os.environ["JWT_SECRET"],
        )
    return TestClient(app), Factory, token("u1", 1), token("u2", 2)


def teardown():
    app.dependency_overrides.clear()


def test_all_business_routes_share_authentication_boundary_and_version():
    client, _, t1, _ = setup_client()
    try:
        h = {"Authorization": f"Bearer {t1}"}
        assert client.get("/health").json()["version"] == "1.0.0"
        protected = [
            "/api/v1/session",
            "/api/v1/dashboard/summary",
            "/api/v1/inventory/stock/i/w",
        ]
        for path in protected:
            assert client.get(path).status_code == 401
        assert client.get("/api/v1/session", headers=h).status_code == 200
        assert client.get("/api/v1/dashboard/summary", headers=h).status_code == 200
    finally:
        teardown()


def test_cross_tenant_resources_are_not_accessible_or_mutable():
    client, Factory, t1, t2 = setup_client()
    try:
        h1 = {"Authorization": f"Bearer {t1}"}
        h2 = {"Authorization": f"Bearer {t2}"}

        assert client.post("/api/v1/inventory/items", json={"id":"i1","name":"Private Item"}, headers=h1).status_code == 201
        assert client.post("/api/v1/inventory/warehouses", json={"id":"w1","name":"Private Warehouse"}, headers=h1).status_code == 201
        assert client.post("/api/v1/purchasing/suppliers", json={"id":"s1","name":"Private Supplier"}, headers=h1).status_code == 201
        assert client.post("/api/v1/inventory/movements", json={"item_id":"i1","warehouse_id":"w1","quantity":"5","direction":"in","reference":"m1"}, headers=h1).status_code == 201

        # Tenant two cannot read tenant one's inventory.
        assert client.get("/api/v1/inventory/stock/i1/w1", headers=h2).status_code == 400

        # Tenant two cannot use tenant one's inventory or supplier to create its own purchase.
        purchase = client.post(
            "/api/v1/purchasing/orders",
            json={"reference":"p2","supplier_id":"s1","warehouse_id":"w1","currency":"YER","lines":[{"item_id":"i1","quantity":"1","unit_cost":"100"}]},
            headers=h2,
        )
        assert purchase.status_code == 400

        # Tenant two's dashboard cannot see tenant one's data.
        summary = client.get("/api/v1/dashboard/summary", headers=h2)
        assert summary.status_code == 200
        data = summary.json()
        assert data["tenant_id"] == 2
        assert data["counts"]["items"] == 0
        assert data["counts"]["inventory_movements"] == 0
        assert data["counts"]["purchase_orders"] == 0

        with Factory() as db:
            assert db.query(__import__('app.core.models.inventory', fromlist=['InventoryItem']).InventoryItem).filter_by(tenant_id=2).count() == 0
    finally:
        teardown()
