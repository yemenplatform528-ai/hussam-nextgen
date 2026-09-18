import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.market import (
    MarketContext, MarketCurrency, MarketMoneyUnit, ProviderRegistryEntry,
    ProviderMarketCapability, PaymentRailRegistryEntry, PaymentAdapterRegistryEntry,
)
from app.engines.market_readiness import evaluate_market_readiness, MarketReadinessStatus
from app.engines.payment_adapters import REQUIRED_PRODUCTION_EVIDENCE


def db_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def seed_market(db, *, status="active"):
    market = MarketContext(code="YE", country_code="YE", name="Yemen", locale="ar-YE", timezone="Asia/Aden", default_currency="YER", status=status)
    db.add(market); db.flush()
    db.add(MarketCurrency(market_id=market.id, currency="YER", is_default=True))
    db.add(MarketMoneyUnit(market_id=market.id, code="YER-CURRENT", currency="YER", variant="current", name="Yemeni Rial Current"))
    db.commit()
    return market.id


def test_missing_market_is_blocked():
    engine, factory = db_factory()
    with factory() as db:
        result = evaluate_market_readiness(db, 999)
        assert result.status is MarketReadinessStatus.BLOCKED
        assert "market_not_found" in result.blockers
    engine.dispose()


def test_active_market_without_external_evidence_is_not_ready():
    engine, factory = db_factory()
    with factory() as db:
        market_id = seed_market(db)
        result = evaluate_market_readiness(db, market_id)
        assert result.status is MarketReadinessStatus.EVIDENCE_REQUIRED
        assert "geography_dataset" in result.evidence_required
        assert "certified_payment_production_path" in result.evidence_required
    engine.dispose()


def test_inactive_market_is_blocked_even_if_configuration_exists():
    engine, factory = db_factory()
    with factory() as db:
        market_id = seed_market(db, status="draft")
        result = evaluate_market_readiness(db, market_id)
        assert result.status is MarketReadinessStatus.BLOCKED
        assert "market_status:draft" in result.blockers
    engine.dispose()
