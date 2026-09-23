from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes.platform import client_market_context
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
        configuration={"offline_drafts": True, "internal_adapter_secret": "hidden"},
    ))
    db.commit()

    result = client_market_context("YEM", Ctx(), db)

    assert result["schema_version"] == "1.0"
    assert result["market"]["code"] == "YEM"
    assert result["money"]["money_units"][0]["code"] == "YER_CURRENT"
    assert result["payments"]["methods"][0]["code"] == "cod"
    assert result["connectivity"]["configuration"]["offline_drafts"] is True
    assert result["capabilities"] == [
        {"code": "yem_connectivity_policy", "category": "connectivity", "status": "active"}
    ]
    assert "internal_secret" not in result["market"]["configuration"]
    assert "internal_adapter_secret" not in result["capabilities"][0]


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
