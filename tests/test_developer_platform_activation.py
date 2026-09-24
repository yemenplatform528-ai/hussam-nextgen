import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.developer_platform import activate_market_capability, CapabilityActivationIn
from app.core.models.market import MarketContext
from app.core.models.yemen_capability import PlatformCapability
from app.core.persistence import Base


def test_market_capability_activation_enforces_declared_configuration_schema():
    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)()
    db.add(MarketContext(
        id=60, code="YEM", country_code="YE", name="Yemen", locale="ar-YE",
        timezone="Asia/Aden", default_currency="YER", status="active",
    ))
    db.add(PlatformCapability(
        id="yem_schema_guard", code="yem_schema_guard", category="test",
        name="Schema guard", market_scope=["YEM"], status="active",
        config_schema={
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["pickup", "delivery"]},
                "offline": {"type": "boolean"},
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    ))
    db.commit()

    class Ctx:
        role = "owner"
        tenant_id = 1
        user_id = "u1"

    with pytest.raises(Exception) as exc:
        activate_market_capability(
            "YEM", "yem_schema_guard",
            CapabilityActivationIn(configuration={"mode": "pickup", "unknown": True}),
            Ctx(), db,
        )
    assert getattr(exc.value, "status_code", None) == 400

    result = activate_market_capability(
        "YEM", "yem_schema_guard",
        CapabilityActivationIn(configuration={"mode": "pickup", "offline": True}),
        Ctx(), db,
    )
    assert result["status"] == "active"
    assert result["configuration"]["offline"] is True
