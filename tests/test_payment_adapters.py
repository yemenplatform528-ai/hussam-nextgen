from decimal import Decimal
import pytest
from app.engines.payment_adapters import (
    PaymentAdapterError, PaymentCreateRequest, PaymentCreateResult,
    PaymentRefundRequest, PaymentRefundResult, PaymentStatusResult,
    StatementRow, UnconfiguredPaymentAdapter,
)


def test_contract_values_are_provider_neutral():
    req = PaymentCreateRequest(reference="PAY-1", amount=Decimal("10.00"), currency="YER")
    assert req.reference == "PAY-1" and req.amount == Decimal("10.00")
    assert PaymentCreateResult("prov-1", "authorized").provider_payment_id == "prov-1"
    assert PaymentStatusResult("prov-1", "captured").status == "captured"
    refund = PaymentRefundRequest("prov-1", "REF-1", Decimal("2"), "YER", "customer")
    assert refund.refund_reference == "REF-1"
    assert PaymentRefundResult("r-1", "succeeded").provider_refund_id == "r-1"
    assert StatementRow("prov-1", Decimal("10"), "YER").status == "posted"


def test_unconfigured_adapter_fails_closed_for_every_operation():
    adapter = UnconfiguredPaymentAdapter("al-kuraimi")
    req = PaymentCreateRequest("PAY-1", Decimal("10"), "YER")
    refund = PaymentRefundRequest("prov-1", "REF-1", Decimal("1"), "YER", "test")
    for call in (
        lambda: adapter.create(req),
        lambda: adapter.get_status("prov-1"),
        lambda: adapter.refund(refund),
        lambda: adapter.import_statement(b"x", source_reference="statement-1"),
    ):
        with pytest.raises(PaymentAdapterError, match="not configured"):
            call()


def test_adapter_requires_a_name():
    with pytest.raises(PaymentAdapterError, match="name"):
        UnconfiguredPaymentAdapter("")
