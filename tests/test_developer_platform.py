import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.developer_platform import validate_manifest
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.developer_platform import DeveloperExtension, DeveloperExtensionVersion
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
