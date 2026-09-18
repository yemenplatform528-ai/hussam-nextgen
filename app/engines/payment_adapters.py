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
