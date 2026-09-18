import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.market import (
    MarketContext, MarketCurrency, MarketMoneyUnit, ProviderRegistryEntry,
    ProviderMarketCapability, PaymentRailRegistryEntry, PaymentAdapterRegistryEntry, MarketReadinessEvidence, MarketGeography,
)
from app.engines.market_readiness import evaluate_market_readiness, build_market_readiness_report, MarketReadinessStatus
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


def test_readiness_report_is_audit_friendly_and_read_only():
    engine, factory = db_factory()
    with factory() as db:
        market_id = seed_market(db)
        before = db.get(MarketContext, market_id).status
        report = build_market_readiness_report(db, market_id)
        assert report.market_code == "YE"
        assert report.market_name == "Yemen"
        assert report.default_currency == "YER"
        assert report.status is MarketReadinessStatus.EVIDENCE_REQUIRED
        assert "geography_dataset" in report.evidence_required
        assert report.ready is False
        assert db.get(MarketContext, market_id).status == before
    engine.dispose()


def test_missing_market_report_remains_blocked_without_inventing_context():
    engine, factory = db_factory()
    with factory() as db:
        report = build_market_readiness_report(db, 404)
        assert report.status is MarketReadinessStatus.BLOCKED
        assert report.market_code is None
        assert report.market_name is None
        assert report.default_currency is None
        assert report.blockers == ("market_not_found",)
    engine.dispose()


def test_accepted_evidence_is_explicit_and_does_not_create_configuration():
    engine, factory = db_factory()
    with factory() as db:
        market_id = seed_market(db)
        from datetime import datetime, timezone
        db.add(MarketReadinessEvidence(
            market_id=market_id,
            requirement_key="geography_dataset",
            status="accepted",
            source_name="Reviewed source",
            source_uri="https://example.invalid/dataset",
            source_sha256="a" * 64,
            license_name="CC-BY-4.0",
            retrieved_at=datetime.now(timezone.utc),
            reviewed_at=datetime.now(timezone.utc),
            reviewer_reference="review-1",
            acceptance_reference="accept-1",
        ))
        db.commit()
        result = evaluate_market_readiness(db, market_id)
        assert "geography_dataset" not in result.evidence_required
        assert db.query(MarketReadinessEvidence).count() == 1
        assert db.query(MarketGeography).count() == 0
    engine.dispose()


def test_accepted_evidence_without_hash_or_acceptance_does_not_count():
    engine, factory = db_factory()
    with factory() as db:
        market_id = seed_market(db)
        from datetime import datetime, timezone
        db.add(MarketReadinessEvidence(
            market_id=market_id,
            requirement_key="geography_dataset",
            status="accepted",
            reviewed_at=datetime.now(timezone.utc),
            acceptance_reference=None,
        ))
        db.commit()
        result = evaluate_market_readiness(db, market_id)
        assert "geography_dataset" in result.evidence_required
    engine.dispose()
