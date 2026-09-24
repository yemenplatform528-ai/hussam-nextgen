import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.models.core import User, Tenant, TenantMembership
from app.core.models.market import MarketContext
from app.core.models.yemen_capability import MarketCapabilityActivation, PlatformCapability
from app.core.persistence import Base


def test_market_capability_activation_actor_uses_user_identity_type():
    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)()

    db.add_all([
        Tenant(id=1, name="Yemen", status="active"),
        User(id="user-123", email="user@example.com", active=True),
    ])
    db.flush()
    db.add(TenantMembership(user_id="user-123", tenant_id=1, role="owner", active=True))
    market = MarketContext(
        id=1, code="YEM", country_code="YE", name="Yemen",
        locale="ar-YE", timezone="Asia/Aden", default_currency="YER",
        status="active",
    )
    capability = PlatformCapability(
        id="yem_delivery_modes", code="yem_delivery_modes",
        category="logistics", name="Yemen delivery modes",
        market_scope=["YEM"], config_schema={}, status="active",
    )
    db.add_all([market, capability])
    db.flush()

    activation = MarketCapabilityActivation(
        id="activation-user-123",
        market_id=1,
        capability_id="yem_delivery_modes",
        status="active",
        configuration={},
        activated_by="user-123",
    )
    db.add(activation)
    db.commit()

    row = db.query(MarketCapabilityActivation).one()
    assert row.activated_by == "user-123"

    column = next(
        c for c in inspect(e).get_columns("market_capability_activations")
        if c["name"] == "activated_by"
    )
    assert isinstance(column["type"], __import__("sqlalchemy").String)
