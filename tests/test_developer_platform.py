import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.developer_platform import validate_manifest
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.developer_platform import DeveloperExtension, DeveloperExtensionVersion
from app.core.models.market import MarketContext
from app.core.models.yemen_capability import MarketCapabilityActivation, PlatformCapability
from app.core.persistence import Base

def test_developer_extension_persistence():
    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)()
    db.add(Tenant(id=1, name="Dev", status="active"))
    db.add(User(id="u1", email="u@example.com", active=True))
    db.add(TenantMembership(user_id="u1", tenant_id=1, role="owner", active=True))
    db.add(DeveloperExtension(
        id="e1",
        tenant_id=1,
        code="yemen.delivery",
        name="Yemen Delivery",
        created_by="u1",
        market_scope=["YEM"],
        capabilities=["logistics.read"],
        permissions=["logistics.read"],
    ))
    db.flush()
    db.add(DeveloperExtensionVersion(
        id="v1",
        extension_id="e1",
        version="1.0.0",
        manifest={"capabilities": ["logistics.read"], "market_scope": ["YEM"]},
        source_hash="a" * 64,
        compatibility={"api": "1.0"},
        created_by="u1",
    ))
    db.commit()
    assert db.query(DeveloperExtension).one().code == "yemen.delivery"
    assert db.query(DeveloperExtensionVersion).one().source_hash == "a" * 64

def test_manifest_cannot_expand_extension_capabilities():
    extension = DeveloperExtension(
        id="e2",
        tenant_id=1,
        code="x",
        name="x",
        created_by="u1",
        capabilities=["catalog.read"],
        permissions=["catalog.read"],
        market_scope=["YEM"],
    )
    with pytest.raises(Exception, match="capability exceeds"):
        validate_manifest(extension, {"capabilities": ["catalog.write"]})

def test_manifest_cannot_expand_market_scope_or_permissions():
    extension = DeveloperExtension(
        id="e3",
        tenant_id=1,
        code="x",
        name="x",
        created_by="u1",
        capabilities=["catalog.read"],
        permissions=["catalog.read"],
        market_scope=["YEM"],
    )
    with pytest.raises(Exception, match="permission exceeds"):
        validate_manifest(extension, {
            "capabilities": ["catalog.read"],
            "permissions": ["catalog.write"],
            "market_scope": ["YEM"],
        })
    with pytest.raises(Exception, match="market scope exceeds"):
        validate_manifest(extension, {
            "capabilities": ["catalog.read"],
            "permissions": ["catalog.read"],
            "market_scope": ["SA"],
        })

def test_manifest_rejects_unknown_surface():
    extension = DeveloperExtension(
        id="e4",
        tenant_id=1,
        code="x",
        name="x",
        created_by="u1",
        capabilities=[],
        permissions=[],
        market_scope=[],
    )
    with pytest.raises(Exception, match="unknown_manifest_keys"):
        validate_manifest(extension, {"shell": "rm -rf"})


def test_market_capability_activation_persistence():
    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)()
    db.add(MarketContext(
        id=10, code="YEM", country_code="YE", name="Yemen", locale="ar-YE",
        timezone="Asia/Aden", default_currency="YER", status="active",
    ))
    db.add(PlatformCapability(
        id="yem_delivery_modes", code="yem_delivery_modes", category="logistics",
        name="Yemen delivery modes", market_scope=["YEM"], config_schema={}, status="active",
    ))
    db.flush()
    db.add(MarketCapabilityActivation(
        id="activation-1", market_id=10, capability_id="yem_delivery_modes",
        status="active", configuration={"modes": ["pickup", "local_delivery"]}, activated_by=1,
    ))
    db.commit()
    row = db.query(MarketCapabilityActivation).one()
    assert row.status == "active"
    assert row.configuration["modes"] == ["pickup", "local_delivery"]


def test_yemen_capability_must_be_registered():
    extension = DeveloperExtension(
        id="e5", tenant_id=1, code="x", name="x", created_by="u1",
        capabilities=["yem_not_registered"], permissions=[], market_scope=["YEM"],
    )
    with pytest.raises(Exception, match="unregistered_yemen_capabilities"):
        validate_manifest(extension, {"capabilities": ["yem_not_registered"]}, registered_codes={"yem_delivery_modes"})


def test_capability_service_validates_registration_and_market_scope():
    from app.core.services.capabilities import CapabilityService

    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)()
    market = MarketContext(
        id=20, code="YEM", country_code="YE", name="Yemen", locale="ar-YE",
        timezone="Asia/Aden", default_currency="YER", status="active",
    )
    capability = PlatformCapability(
        id="yem_money_presentation", code="yem_money_presentation",
        category="money", name="Yemen money presentation",
        market_scope=["YEM"], config_schema={}, status="active",
    )
    db.add_all([market, capability])
    db.flush()

    service = CapabilityService(db)
    assert service.active_codes() == {"yem_money_presentation"}
    assert service.get_active("yem_money_presentation").code == "yem_money_presentation"
    service.validate_registered(["yem_money_presentation"])
    service.validate_market_scope(market, capability)

    with pytest.raises(ValueError, match="unregistered_capabilities"):
        service.validate_registered(["yem_missing"])

    market.status = "suspended"
    with pytest.raises(ValueError, match="market must be active"):
        service.validate_market_scope(market, capability)

    market.status = "active"
    capability.market_scope = ["SA"]
    with pytest.raises(ValueError, match="not scoped"):
        service.validate_market_scope(market, capability)


def test_capability_service_reads_market_activation_state():
    from app.core.services.capabilities import CapabilityService

    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)()
    market = MarketContext(
        id=30, code="YEM", country_code="YE", name="Yemen", locale="ar-YE",
        timezone="Asia/Aden", default_currency="YER", status="active",
    )
    capability = PlatformCapability(
        id="yem_connectivity_policy", code="yem_connectivity_policy",
        category="connectivity", name="Yemen connectivity policy",
        market_scope=["YEM"], config_schema={}, status="active",
    )
    db.add_all([market, capability])
    db.flush()
    db.add(MarketCapabilityActivation(
        id="activation-30", market_id=30, capability_id="yem_connectivity_policy",
        status="active", configuration={"offline_safe": True},
    ))
    db.commit()

    service = CapabilityService(db)
    assert service.is_active_for_market(market, "yem_connectivity_policy") is True
    rows = service.list_market_activations(market)
    assert len(rows) == 1
    assert rows[0][1].code == "yem_connectivity_policy"

    activation = rows[0][0]
    activation.status = "suspended"
    db.commit()
    assert service.is_active_for_market(market, "yem_connectivity_policy") is False
