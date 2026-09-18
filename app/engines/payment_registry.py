"""Fail-closed registry resolution for payment rails and adapters."""
from dataclasses import dataclass
from sqlalchemy import select, or_
from app.core.models.market import PaymentAdapterRegistryEntry, PaymentRailRegistryEntry, ProviderRegistryEntry
from app.engines.payment_adapters import evaluate_provider_production_gate

@dataclass(frozen=True)
class PaymentAdapterResolution:
    allowed: bool
    provider_code: str
    rail: str
    currency: str
    adapter_code: str | None = None
    adapter_version: str | None = None
    blocked_reasons: tuple[str, ...] = ()


def resolve_payment_adapter(db, provider_code: str, market_id: int, capability: str, rail: str, currency: str) -> PaymentAdapterResolution:
    """Resolve only an active production adapter whose rail and provider gates pass."""
    reasons: list[str] = []
    provider = db.scalar(select(ProviderRegistryEntry).where(ProviderRegistryEntry.code == provider_code))
    if provider is None:
        return PaymentAdapterResolution(False, provider_code, rail, currency, blocked_reasons=("provider_not_registered",))

    gate = evaluate_provider_production_gate(db, provider_code, market_id, capability, rail=rail, currency=currency)
    if not gate.allowed:
        reasons.extend(gate.blocked_reasons)

    rail_entry = db.scalar(select(PaymentRailRegistryEntry).where(
        PaymentRailRegistryEntry.market_id == market_id,
        PaymentRailRegistryEntry.code == rail,
        PaymentRailRegistryEntry.capability == capability,
        or_(PaymentRailRegistryEntry.currency == currency, PaymentRailRegistryEntry.currency == ""),
        PaymentRailRegistryEntry.status.in_(("certified", "production")),
    ))
    if rail_entry is None:
        reasons.append("rail_not_certified_for_market")
        return PaymentAdapterResolution(False, provider_code, rail, currency, blocked_reasons=tuple(dict.fromkeys(reasons)))

    adapter = db.scalar(select(PaymentAdapterRegistryEntry).where(
        PaymentAdapterRegistryEntry.provider_id == provider.id,
        PaymentAdapterRegistryEntry.rail_id == rail_entry.id,
        PaymentAdapterRegistryEntry.active.is_(True),
        PaymentAdapterRegistryEntry.status == "production",
    ))
    if adapter is None:
        reasons.append("production_adapter_not_active")

    if reasons:
        return PaymentAdapterResolution(False, provider_code, rail, currency, blocked_reasons=tuple(dict.fromkeys(reasons)))
    return PaymentAdapterResolution(True, provider_code, rail, currency, adapter.adapter_code, adapter.adapter_version)
