from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.platform import _public_runtime_context, client_market_context
from app.core.models.market import MarketContext, MarketCurrency, MarketMoneyUnit, PaymentMethodCatalogEntry
from app.core.models.yemen_capability import MarketCapabilityActivation, PlatformCapability
from app.core.persistence import Base


class Ctx:
    tenant_id = 1
    user_id = "u1"


def test_client_market_context_is_stable_and_hides_control_plane_configuration():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(engine, expire_on_commit=False)()

    market = MarketContext(
        id=1, code="YEM", country_code="YE", name="Yemen", locale="ar-YE",
        timezone="Asia/Aden", default_currency="YER", status="active",
        configuration_json='{"client_label":"Yemen","internal_secret":"must-not-leak"}',
    )
    currency = MarketCurrency(
        id=2, market_id=1, currency="YER", is_default=True,
        cash_supported=True, electronic_supported=True,
    )
    unit = MarketMoneyUnit(
        id=3, market_id=1, code="YER_CURRENT", currency="YER",
        variant="current", name="Yemeni rial", name_ar="ريال يمني", status="active",
        metadata_json='{"internal_adapter_secret":"must-not-leak"}',
    )
    cod = PaymentMethodCatalogEntry(
        id=4, market_id=1, code="cod", name="Cash on delivery",
        method_type="cod", requires_provider=False, active=True,
    )
    capability = PlatformCapability(
        id="yem_connectivity_policy", code="yem_connectivity_policy",
        category="connectivity", name="Connectivity", market_scope=["YEM"],
        config_schema={}, status="active",
    )
    db.add_all([market, currency, unit, cod, capability])
    db.flush()
    db.add(MarketCapabilityActivation(
        id="a1", market_id=1, capability_id=capability.id, status="active",
        configuration={
            "offline_drafts": True,
            "idempotent_mutations": True,
            "explicit_pending_states": True,
            "internal_adapter_secret": "hidden",
        },
    ))
    for code, category, config in [
        ("yem_local_pricing", "pricing", {"enabled": True, "modes": ["retail", "wholesale"], "branch_overrides": True}),
        ("yem_business_verticals", "verticals", {"enabled": True, "verticals": ["retail", "clinic"]}),
        ("yem_branch_warehouse_network", "operations", {"enabled": True, "branch_aware": True, "warehouse_aware": True, "service_area_aware": True}),
        ("yem_local_reporting", "analytics", {"enabled": True, "dimensions": ["governorate", "channel"]}),
    ]:
        cap = PlatformCapability(
            id=code, code=code, category=category, name=code, market_scope=["YEM"],
            config_schema={}, status="active",
        )
        db.add(cap)
        db.flush()
        db.add(MarketCapabilityActivation(
            id=f"activation-{code}", market_id=1, capability_id=code, status="active",
            configuration=config,
        ))
    db.commit()

    result = client_market_context("YEM", Ctx(), db)

    assert result["schema_version"] == "1.0"
    assert result["market"]["code"] == "YEM"
    assert result["money"]["money_units"][0]["code"] == "YER_CURRENT"
    assert "metadata" not in result["money"]["money_units"][0]
    assert result["payments"]["methods"][0]["code"] == "cod"
    assert result["connectivity"] == {
        "offline_drafts": True,
        "idempotent_mutations": True,
        "explicit_pending_states": True,
    }
    assert result["pricing"] == {
        "enabled": True, "modes": ["retail", "wholesale"], "branch_overrides": True,
    }
    assert result["verticals"] == {"enabled": True, "verticals": ["retail", "clinic"]}
    assert result["operations"] == {
        "enabled": True, "branch_aware": True, "warehouse_aware": True,
        "service_area_aware": True,
    }
    assert result["reporting"] == {
        "enabled": True, "dimensions": ["governorate", "channel"],
    }
    assert result["capabilities"] == [
        {"code": "yem_connectivity_policy", "category": "connectivity", "status": "active"}
    ]
    assert "configuration" not in result["market"]
    assert "internal_secret" not in result["market"]
    assert "internal_adapter_secret" not in str(result)


def test_client_market_context_rejects_inactive_market():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db = sessionmaker(engine, expire_on_commit=False)()
    db.add(MarketContext(
        id=2, code="YEM", country_code="YE", name="Yemen", locale="ar-YE",
        timezone="Asia/Aden", default_currency="YER", status="suspended",
    ))
    db.commit()

    try:
        client_market_context("YEM", Ctx(), db)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("inactive market must be rejected")


def test_public_market_context_geography_is_allow_listed():
    runtime = {
        "market": {
            "code": "YEM", "country_code": "YE", "name": "Yemen",
            "locale": "ar-YE", "timezone": "Asia/Aden",
            "default_currency": "YER", "status": "active",
        },
        "money": {"currencies": [], "money_units": []},
        "payments": {"methods": []},
        "geography": {
            "coverage": [{
                "code": "YE-TA", "level": "governorate", "name": "Taiz",
                "name_ar": "تعز", "status": "available",
                "internal_secret": "must-not-leak",
            }],
            "internal_control_plane": "must-not-leak",
        },
        "delivery": {"configuration": {}},
        "connectivity": {"configuration": {}},
        "documents": {"configuration": {}, "lifecycle": [], "versioned": False, "immutable_versions": False},
        "notifications": {"configuration": {}},
        "ai_hus": {"configuration": {}, "market_context": {}, "governance": {}},
        "capabilities": [],
    }
    result = _public_runtime_context(runtime)
    assert result["geography"] == {
        "coverage": [{
            "code": "YE-TA", "level": "governorate", "name": "Taiz",
            "name_ar": "تعز", "status": "available",
        }]
    }
    assert "internal_secret" not in str(result)
    assert "internal_control_plane" not in str(result)

def test_public_market_context_exposes_remaining_capability_contracts_only():
    runtime = {
        "market": {"code": "YEM", "country_code": "YE", "name": "Yemen", "locale": "ar-YE", "timezone": "Asia/Aden", "default_currency": "YER", "status": "active"},
        "money": {"currencies": [], "money_units": []},
        "payments": {"methods": []},
        "geography": {"coverage": []},
        "delivery": {"configuration": {}},
        "connectivity": {"configuration": {}},
        "documents": {"configuration": {}, "lifecycle": [], "versioned": False, "immutable_versions": False},
        "notifications": {"configuration": {}},
        "ai_hus": {"configuration": {},"market_context": {}, "governance": {}},
        "pricing": {"enabled": True, "modes": ["retail", "wholesale"], "branch_overrides": True, "internal": "hidden"},
        "verticals": {"enabled": True, "verticals": ["retail", "clinic"], "internal": "hidden"},
        "operations": {"enabled": True, "branch_aware": True, "warehouse_aware": True, "service_area_aware": True, "internal": "hidden"},
        "reporting": {"enabled": True, "dimensions": ["governorate", "channel"], "internal": "hidden"},
        "capabilities": [],
    }
    result = _public_runtime_context(runtime)
    assert result["pricing"] == {"enabled": True, "modes": ["retail", "wholesale"], "branch_overrides": True}
    assert result["verticals"] == {"enabled": True, "verticals": ["retail", "clinic"]}
    assert result["operations"] == {"enabled": True, "branch_aware": True, "warehouse_aware": True, "service_area_aware": True}
    assert result["reporting"] == {"enabled": True, "dimensions": ["governorate", "channel"]}
    assert "internal" not in str(result)