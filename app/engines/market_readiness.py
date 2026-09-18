"""Fail-closed market activation readiness evaluation.

This module evaluates whether a market can be activated without inventing
national geography, FX, provider integrations, or external evidence.
"""
from dataclasses import dataclass
from enum import Enum
import json
from sqlalchemy import select

from app.core.models.market import (
    MarketContext,
    MarketCurrency,
    MarketGeography,
    MarketMoneyUnit,
    MarketExchangeRate,
    MarketCoverage,
    ProviderRegistryEntry,
    ProviderMarketCapability,
    PaymentRailRegistryEntry,
    PaymentAdapterRegistryEntry,
    MarketReadinessEvidence,
)
from app.engines.payment_adapters import REQUIRED_PRODUCTION_EVIDENCE


class MarketReadinessStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"


@dataclass(frozen=True)
class MarketReadiness:
    market_id: int
    status: MarketReadinessStatus
    checks: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_required: tuple[str, ...]


@dataclass(frozen=True)
class MarketReadinessReport:
    """Audit-friendly, read-only view of one market's activation readiness."""

    market_id: int
    status: MarketReadinessStatus
    market_code: str | None
    market_name: str | None
    default_currency: str | None
    checks: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_required: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.status is MarketReadinessStatus.READY


def _payment_production_ready(db, market_id: int) -> bool:
    rows = db.execute(
        select(ProviderRegistryEntry, ProviderMarketCapability)
        .join(ProviderMarketCapability, ProviderMarketCapability.provider_id == ProviderRegistryEntry.id)
        .where(
            ProviderMarketCapability.market_id == market_id,
            ProviderMarketCapability.capability == "payment",
            ProviderMarketCapability.active.is_(True),
            ProviderRegistryEntry.provider_type == "payment",
            ProviderRegistryEntry.status == "production",
        )
    ).all()
    for provider, capability in rows:
        try:
            evidence = json.loads(provider.metadata_json or "{}")
        except (TypeError, ValueError):
            continue
        if any(evidence.get(key) is not True for key in REQUIRED_PRODUCTION_EVIDENCE):
            continue
        rails = db.scalars(
            select(PaymentRailRegistryEntry).where(
                PaymentRailRegistryEntry.market_id == market_id,
                PaymentRailRegistryEntry.capability == "payment",
                PaymentRailRegistryEntry.status == "production",
            )
        ).all()
        for rail in rails:
            adapters = db.scalars(
                select(PaymentAdapterRegistryEntry).where(
                    PaymentAdapterRegistryEntry.provider_id == provider.id,
                    PaymentAdapterRegistryEntry.rail_id == rail.id,
                    PaymentAdapterRegistryEntry.status == "production",
                    PaymentAdapterRegistryEntry.active.is_(True),
                )
            ).all()
            if adapters:
                return True
    return False


def _accepted_evidence(db, market_id: int) -> set[str]:
    rows = db.scalars(
        select(MarketReadinessEvidence).where(
            MarketReadinessEvidence.market_id == market_id,
            MarketReadinessEvidence.status == "accepted",
        )
    ).all()
    accepted: set[str] = set()
    for row in rows:
        if row.source_sha256 and row.reviewed_at and row.acceptance_reference:
            accepted.add(row.requirement_key)
    return accepted


def evaluate_market_readiness(db, market_id: int) -> MarketReadiness:
    """Return a conservative activation decision for one market."""
    checks: list[str] = []
    blockers: list[str] = []
    evidence: list[str] = []
    accepted_evidence = _accepted_evidence(db, market_id)

    def require_evidence(key: str) -> None:
        if key not in accepted_evidence:
            evidence.append(key)

    market = db.scalar(select(MarketContext).where(MarketContext.id == market_id))
    if market is None:
        return MarketReadiness(market_id, MarketReadinessStatus.BLOCKED, (), ("market_not_found",), ())
    if market.status != "active":
        blockers.append(f"market_status:{market.status}")
    else:
        checks.append("market_active")

    currency = db.scalar(select(MarketCurrency).where(
        MarketCurrency.market_id == market_id,
        MarketCurrency.currency == market.default_currency,
    ))
    if currency is None or not (currency.cash_supported or currency.electronic_supported):
        blockers.append("default_currency_not_enabled")
    else:
        checks.append("default_currency_enabled")

    money_unit = db.scalar(select(MarketMoneyUnit).where(
        MarketMoneyUnit.market_id == market_id,
        MarketMoneyUnit.currency == market.default_currency,
        MarketMoneyUnit.status == "active",
    ))
    if money_unit is None:
        require_evidence("money_unit_definition")
    else:
        checks.append("money_unit_defined")

    geography_count = db.scalar(select(MarketGeography.id).where(MarketGeography.market_id == market_id).limit(1))
    if geography_count is None:
        require_evidence("geography_dataset")
    else:
        checks.append("geography_present")
        coverage_count = db.scalar(select(MarketCoverage.id).where(MarketCoverage.market_id == market_id).limit(1))
        if coverage_count is None:
            require_evidence("operational_coverage")
        else:
            checks.append("operational_coverage_present")

    # FX is evidence-driven; do not require an FX table for same-currency commerce.
    if market.default_currency:
        checks.append("fx_not_required_for_same_currency")

    if _payment_production_ready(db, market_id):
        checks.append("payment_production_path")
    else:
        require_evidence("certified_payment_production_path")

    if blockers:
        status = MarketReadinessStatus.BLOCKED
    elif evidence:
        status = MarketReadinessStatus.EVIDENCE_REQUIRED
    else:
        status = MarketReadinessStatus.READY
    return MarketReadiness(market_id, status, tuple(checks), tuple(blockers), tuple(evidence))


def build_market_readiness_report(db, market_id: int) -> MarketReadinessReport:
    """Build a deterministic, read-only readiness report for audit/review.

    This intentionally reuses the same fail-closed evaluator and adds only
    market identity/context. It never mutates market configuration or creates
    evidence, geography, FX rates, providers, rails, or adapters.
    """
    market = db.scalar(select(MarketContext).where(MarketContext.id == market_id))
    readiness = evaluate_market_readiness(db, market_id)
    return MarketReadinessReport(
        market_id=market_id,
        status=readiness.status,
        market_code=market.code if market else None,
        market_name=market.name if market else None,
        default_currency=market.default_currency if market else None,
        checks=readiness.checks,
        blockers=readiness.blockers,
        evidence_required=readiness.evidence_required,
    )
