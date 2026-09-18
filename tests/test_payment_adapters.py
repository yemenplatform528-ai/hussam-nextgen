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


def test_provider_production_gate_fails_closed_without_registry_evidence():
    from app.core.models.market import ProviderRegistryEntry, ProviderMarketCapability
    from app.engines.payment_adapters import evaluate_provider_production_gate, REQUIRED_PRODUCTION_EVIDENCE
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.persistence import Base
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        provider = ProviderRegistryEntry(
            code="demo-provider", organization_name="Demo", provider_type="payment",
            product_name="Demo Pay", status="production", integration_mode="api", metadata_json="{}"
        )
        db.add(provider); db.flush()
        db.add(ProviderMarketCapability(provider_id=provider.id, market_id=1, capability="payment", active=True))
        db.commit()
        gate = evaluate_provider_production_gate(db, "demo-provider", 1, "payment")
        assert not gate.allowed
        assert any(x.startswith("missing_evidence:") for x in gate.blocked_reasons)
        assert len(REQUIRED_PRODUCTION_EVIDENCE) == 11
    engine.dispose()


def test_provider_production_gate_allows_only_complete_evidence_and_capability():
    import json
    from app.core.models.market import ProviderRegistryEntry, ProviderMarketCapability
    from app.engines.payment_adapters import evaluate_provider_production_gate, REQUIRED_PRODUCTION_EVIDENCE
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.persistence import Base
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        evidence = json.dumps({key: True for key in REQUIRED_PRODUCTION_EVIDENCE})
        provider = ProviderRegistryEntry(
            code="certified-provider", organization_name="Certified", provider_type="payment",
            product_name="Certified Pay", status="production", integration_mode="api", metadata_json=evidence
        )
        db.add(provider); db.flush()
        db.add(ProviderMarketCapability(provider_id=provider.id, market_id=1, capability="payment", rail="wallet", currency="YER", active=True))
        db.commit()
        assert evaluate_provider_production_gate(db, "certified-provider", 1, "payment", rail="wallet", currency="YER").allowed
        assert not evaluate_provider_production_gate(db, "certified-provider", 1, "payment").allowed
    engine.dispose()
