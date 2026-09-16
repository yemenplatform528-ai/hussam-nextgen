from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class PaymentIntent(Base):
    __tablename__ = 'payment_intents'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[str] = mapped_column(String(4000), nullable=False, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'reference', name='uq_payment_intent_tenant_reference'),
        UniqueConstraint('tenant_id', 'provider', 'provider_payment_id', name='uq_payment_intent_provider_payment'),
        CheckConstraint('amount > 0', name='ck_payment_intent_positive_amount'),
        CheckConstraint("status IN ('pending','processing','authorized','captured','failed','cancelled','refunded')", name='ck_payment_intent_status'),
    )
class PaymentRefund(Base):
    __tablename__ = 'payment_refunds'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    payment_reference: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    refund_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='requested')
    provider_refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint('tenant_id','refund_reference', name='uq_payment_refund_reference'),
        UniqueConstraint('tenant_id','provider_refund_id', name='uq_payment_refund_provider_ref'),
        CheckConstraint('amount > 0', name='ck_payment_refund_positive_amount'),
        CheckConstraint("status IN ('requested','processing','succeeded','failed','cancelled')", name='ck_payment_refund_status'),
    )




class PaymentWebhook(Base):
    __tablename__ = 'payment_webhooks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[str] = mapped_column(String(10000), nullable=False, default='{}')
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'provider', 'event_id', name='uq_payment_webhook_event'),)


class PaymentSettlement(Base):
    __tablename__ = 'payment_settlements'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    settlement_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'settlement_reference', name='uq_payment_settlement_tenant_reference'),
        CheckConstraint('amount > 0', name='ck_payment_settlement_positive_amount'),
        CheckConstraint("status IN ('pending','settled','reversed')", name='ck_payment_settlement_status'),
    )


class PaymentReconciliation(Base):
    __tablename__ = 'payment_reconciliations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_amount: Mapped[object | None] = mapped_column(Numeric(20,4), nullable=True)
    actual_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    details_json: Mapped[str] = mapped_column(String(4000), nullable=False, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'provider', 'provider_reference', name='uq_payment_reconciliation_provider_ref'),
        CheckConstraint("status IN ('matched','amount_mismatch','currency_mismatch','unknown')", name='ck_payment_reconciliation_status'),
    )
