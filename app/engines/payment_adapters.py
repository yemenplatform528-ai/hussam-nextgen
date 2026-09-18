"""Provider adapter contracts for the governed payment boundary.

Adapters translate an external provider's protocol into Hussam's neutral contract.
They must not write authoritative finance, mutate payment state directly, or store
provider credentials in the core database.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Protocol, Sequence


class PaymentAdapterError(ValueError):
    """Expected provider/adaptor failure that is safe to classify upstream."""


@dataclass(frozen=True)
class PaymentCreateRequest:
    reference: str
    amount: Decimal
    currency: str
    callback_reference: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentCreateResult:
    provider_payment_id: str
    status: str
    provider_reference: str | None = None


@dataclass(frozen=True)
class PaymentStatusResult:
    provider_payment_id: str
    status: str
    provider_reference: str | None = None
    amount: Decimal | None = None
    currency: str | None = None


@dataclass(frozen=True)
class PaymentRefundRequest:
    provider_payment_id: str
    refund_reference: str
    amount: Decimal
    currency: str
    reason: str


@dataclass(frozen=True)
class PaymentRefundResult:
    provider_refund_id: str
    status: str


@dataclass(frozen=True)
class StatementRow:
    provider_reference: str
    amount: Decimal
    currency: str
    status: str = "posted"
    metadata: Mapping[str, str] = field(default_factory=dict)


class PaymentAdapter(Protocol):
    """Minimal provider boundary; implementations remain outside the core."""

    name: str

    def create(self, request: PaymentCreateRequest) -> PaymentCreateResult: ...

    def get_status(self, provider_payment_id: str) -> PaymentStatusResult: ...

    def refund(self, request: PaymentRefundRequest) -> PaymentRefundResult: ...

    def import_statement(self, source: bytes, *, source_reference: str) -> Sequence[StatementRow]: ...


class UnconfiguredPaymentAdapter:
    """Explicit fail-closed adapter used until a provider is certified."""

    def __init__(self, name: str):
        if not name:
            raise PaymentAdapterError("adapter name is required")
        self.name = name

    def _fail(self) -> None:
        raise PaymentAdapterError(f"payment adapter '{self.name}' is not configured")

    def create(self, request: PaymentCreateRequest) -> PaymentCreateResult:
        self._fail()

    def get_status(self, provider_payment_id: str) -> PaymentStatusResult:
        self._fail()

    def refund(self, request: PaymentRefundRequest) -> PaymentRefundResult:
        self._fail()

    def import_statement(self, source: bytes, *, source_reference: str) -> Sequence[StatementRow]:
        self._fail()

@dataclass(frozen=True)
class ProviderProductionGate:
    """Fail-closed decision for whether a provider rail may execute in production."""

    allowed: bool
    provider: str
    market_id: int
    capability: str
    blocked_reasons: tuple[str, ...] = ()


REQUIRED_PRODUCTION_EVIDENCE = (
    "identity_licensing",
    "capability",
    "market_currency_scope",
    "commercial_basis",
    "technical_interface",
    "authentication",
    "webhook_semantics",
    "idempotency",
    "settlement_reconciliation",
    "certification",
    "operational_owner",
)


def evaluate_provider_production_gate(db, provider_code: str, market_id: int, capability: str, *, rail: str = "", currency: str = "") -> ProviderProductionGate:
    """Evaluate catalog + capability + evidence; never infer production access."""
    import json
    from sqlalchemy import select
    from app.core.models.market import ProviderMarketCapability, ProviderRegistryEntry

    reasons: list[str] = []
    provider = db.scalar(select(ProviderRegistryEntry).where(ProviderRegistryEntry.code == provider_code))
    if provider is None:
        reasons.append("provider_not_registered")
        return ProviderProductionGate(False, provider_code, market_id, capability, tuple(reasons))

    if provider.status != "production":
        reasons.append(f"provider_status:{provider.status}")
    if provider.integration_mode == "none":
        reasons.append("integration_mode:none")

    cap = db.scalar(select(ProviderMarketCapability).where(
        ProviderMarketCapability.provider_id == provider.id,
        ProviderMarketCapability.market_id == market_id,
        ProviderMarketCapability.capability == capability,
        ProviderMarketCapability.rail == rail,
        ProviderMarketCapability.currency == currency,
        ProviderMarketCapability.active.is_(True),
    ))
    if cap is None:
        reasons.append("market_capability_not_active")

    try:
        evidence = json.loads(provider.metadata_json or "{}")
    except (TypeError, ValueError):
        evidence = {}
        reasons.append("invalid_evidence_metadata")
    missing = [key for key in REQUIRED_PRODUCTION_EVIDENCE if evidence.get(key) is not True]
    reasons.extend(f"missing_evidence:{key}" for key in missing)

    return ProviderProductionGate(not reasons, provider.code, market_id, capability, tuple(reasons))
