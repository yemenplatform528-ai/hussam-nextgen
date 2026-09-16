from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.payments import PaymentIntent, PaymentWebhook, PaymentSettlement, PaymentReconciliation, PaymentRefund
from app.core.models.governance import OutboxEvent
from app.core.models.core import Journal
from app.engines.finance.production import PostingLine, post_journal


class PaymentError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderPaymentResult:
    provider_payment_id: str
    status: str


class PaymentProvider(Protocol):
    name: str
    def create_payment(self, *, reference: str, amount: Decimal, currency: str) -> ProviderPaymentResult: ...


class PaymentProductionService:
    """Provider-agnostic payment lifecycle. Providers never write authoritative finance directly."""
    def __init__(self, db: Session):
        self.db = db

    def _event(self, tenant_id, event_type, aggregate_id, payload):
        from uuid import uuid4
        self.db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type,
                                aggregate_type='payment', aggregate_id=str(aggregate_id), payload=payload, published=False))

    def create_intent(self, tenant_id: int, reference: str, provider: str, amount: Decimal, currency: str, *, commit: bool = True) -> PaymentIntent:
        amount = Decimal(str(amount))
        if tenant_id <= 0 or not reference or not provider or not currency or amount <= 0:
            raise PaymentError('valid tenant, reference, provider, currency and positive amount are required')
        if self.db.scalar(select(PaymentIntent).where(PaymentIntent.tenant_id == tenant_id, PaymentIntent.reference == reference)):
            raise PaymentError('duplicate payment reference')
        p = PaymentIntent(tenant_id=tenant_id, reference=reference, provider=provider, amount=amount,
                          currency=currency, status='pending')
        self.db.add(p); self.db.flush()
        self._event(tenant_id, 'payments.intent.created', p.id,
                    {'reference': reference, 'provider': provider, 'amount': str(amount), 'currency': currency})
        if not commit:
            return p
        try:
            self.db.commit(); self.db.refresh(p); return p
        except IntegrityError:
            self.db.rollback(); raise PaymentError('duplicate payment reference')

    def mark_processing(self, tenant_id: int, payment_reference: str) -> PaymentIntent:
        p = self._get(tenant_id, payment_reference, lock=True)
        if p.status != 'pending': raise PaymentError('payment is not pending')
        p.status = 'processing'; p.updated_at = datetime.now(timezone.utc)
        self._event(tenant_id, 'payments.intent.processing', p.id, {'reference': p.reference})
        self.db.commit(); return p

    def attach_provider_payment(self, tenant_id: int, payment_reference: str, provider_payment_id: str) -> PaymentIntent:
        if not provider_payment_id: raise PaymentError('provider payment id is required')
        p = self._get(tenant_id, payment_reference, lock=True)
        if p.provider_payment_id and p.provider_payment_id != provider_payment_id:
            raise PaymentError('provider payment id cannot be changed')
        conflict = self.db.scalar(select(PaymentIntent).where(
            PaymentIntent.tenant_id == tenant_id, PaymentIntent.provider == p.provider,
            PaymentIntent.provider_payment_id == provider_payment_id, PaymentIntent.id != p.id))
        if conflict: raise PaymentError('provider payment id already belongs to another payment')
        p.provider_payment_id = provider_payment_id
        p.updated_at = datetime.now(timezone.utc)
        self.db.commit(); return p

    def _get(self, tenant_id, reference, lock=False):
        q = select(PaymentIntent).where(PaymentIntent.tenant_id == tenant_id, PaymentIntent.reference == reference)
        if lock: q = q.with_for_update()
        p = self.db.scalar(q)
        if p is None: raise PaymentError('payment not found in tenant')
        return p

    def process_webhook(self, tenant_id: int, *, provider: str, event_id: str, event_type: str,
                        payment_reference: str, provider_payment_id: str | None = None,
                        status: str | None = None, payload: dict | None = None) -> PaymentWebhook:
        if not provider or not event_id or not event_type or not payment_reference:
            raise PaymentError('webhook identity fields are required')
        existing = self.db.scalar(select(PaymentWebhook).where(
            PaymentWebhook.tenant_id == tenant_id, PaymentWebhook.provider == provider,
            PaymentWebhook.event_id == event_id))
        if existing:
            return existing
        p = self._get(tenant_id, payment_reference, lock=True)
        if p.provider != provider:
            raise PaymentError('provider mismatch')
        if provider_payment_id:
            if p.provider_payment_id and p.provider_payment_id != provider_payment_id:
                raise PaymentError('provider payment id cannot be changed')
            conflict = self.db.scalar(select(PaymentIntent).where(
                PaymentIntent.tenant_id == tenant_id, PaymentIntent.provider == provider,
                PaymentIntent.provider_payment_id == provider_payment_id, PaymentIntent.id != p.id))
            if conflict:
                raise PaymentError('provider payment id already belongs to another payment')
            p.provider_payment_id = provider_payment_id
        allowed = {'processing','authorized','captured','failed','cancelled','refunded'}
        if status is not None:
            if status not in allowed: raise PaymentError('unsupported payment status')
            if p.status == 'captured' and status not in {'captured','refunded'}:
                raise PaymentError('captured payment cannot move backwards')
            if p.status == 'refunded' and status != 'refunded':
                raise PaymentError('refunded payment is terminal')
            p.status = status
            p.updated_at = datetime.now(timezone.utc)
        hook = PaymentWebhook(tenant_id=tenant_id, provider=provider, event_id=event_id,
                              event_type=event_type, payment_reference=payment_reference,
                              payload_json=json.dumps(payload or {}, sort_keys=True), processed=True)
        self.db.add(hook)
        self._event(tenant_id, f'payments.webhook.{event_type}', p.id,
                    {'reference': p.reference, 'provider': provider, 'event_id': event_id, 'status': p.status})
        try:
            self.db.commit(); self.db.refresh(hook); return hook
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(PaymentWebhook).where(
                PaymentWebhook.tenant_id == tenant_id, PaymentWebhook.provider == provider,
                PaymentWebhook.event_id == event_id))
            if existing: return existing
            raise PaymentError('webhook event conflict')

    def capture(self, tenant_id: int, payment_reference: str, *, posting_date: date,
                clearing_account: str = 'payment_clearing', receivable_account: str = 'accounts_receivable',
                actor_id: str | None = None) -> PaymentIntent:
        p = self._get(tenant_id, payment_reference, lock=True)
        if p.status not in {'authorized', 'processing'}:
            raise PaymentError('only authorized or processing payments can be captured')
        if not p.provider_payment_id:
            raise PaymentError('provider payment must be verified before capture')
        # Accounting is authoritative only after provider verification is represented by provider_payment_id + status.
        post_journal(self.db, tenant_id=tenant_id, reference=f'PAY:{p.reference}:capture', currency=p.currency,
                     posting_date=posting_date, actor_id=actor_id,
                     lines=[PostingLine(clearing_account, debit=Decimal(str(p.amount))),
                            PostingLine(receivable_account, credit=Decimal(str(p.amount)))])
        p.status = 'captured'; p.updated_at = datetime.now(timezone.utc)
        self._event(tenant_id, 'payments.captured', p.id,
                    {'reference': p.reference, 'amount': str(p.amount), 'currency': p.currency})
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return p

    def settle(self, tenant_id: int, payment_reference: str, *, settlement_reference: str,
               actual_amount: Decimal, currency: str, posting_date: date,
               cash_account: str = 'cash', clearing_account: str = 'payment_clearing',
               actor_id: str | None = None) -> PaymentSettlement:
        p = self._get(tenant_id, payment_reference, lock=True)
        if p.status != 'captured': raise PaymentError('only captured payments can be settled')
        amount = Decimal(str(actual_amount))
        if amount != Decimal(str(p.amount)) or currency != p.currency:
            raise PaymentError('settlement amount/currency does not match captured payment')
        if self.db.scalar(select(PaymentSettlement).where(PaymentSettlement.tenant_id == tenant_id,
                                                          PaymentSettlement.settlement_reference == settlement_reference)):
            raise PaymentError('duplicate settlement reference')
        s = PaymentSettlement(tenant_id=tenant_id, provider=p.provider, settlement_reference=settlement_reference,
                              payment_reference=p.reference, amount=amount, currency=currency,
                              status='settled', settled_at=datetime.now(timezone.utc))
        self.db.add(s); self.db.flush()
        post_journal(self.db, tenant_id=tenant_id, reference=f'SET:{settlement_reference}', currency=currency,
                     posting_date=posting_date, actor_id=actor_id,
                     lines=[PostingLine(cash_account, debit=amount), PostingLine(clearing_account, credit=amount)])
        self._event(tenant_id, 'payments.settled', s.id,
                    {'payment_reference': p.reference, 'settlement_reference': settlement_reference, 'amount': str(amount), 'currency': currency})
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(s)
        return s
    def create_refund(self, tenant_id: int, payment_reference: str, *, refund_reference: str, amount: Decimal, currency: str, reason: str) -> PaymentRefund:
        p = self._get(tenant_id, payment_reference, lock=True)
        if p.status != 'captured':
            raise PaymentError('only captured payments can be refunded')
        amount = Decimal(str(amount))
        if amount <= 0 or amount > Decimal(str(p.amount)):
            raise PaymentError('refund amount must be positive and not exceed captured payment')
        if currency != p.currency:
            raise PaymentError('refund currency does not match payment')
        existing = self.db.scalar(select(PaymentRefund).where(PaymentRefund.tenant_id == tenant_id, PaymentRefund.refund_reference == refund_reference))
        if existing:
            raise PaymentError('duplicate refund reference')
        prior = self.db.scalars(select(PaymentRefund).where(PaymentRefund.tenant_id == tenant_id, PaymentRefund.payment_reference == payment_reference, PaymentRefund.status == 'succeeded')).all()
        refunded = sum((Decimal(str(x.amount)) for x in prior), Decimal('0'))
        if refunded + amount > Decimal(str(p.amount)):
            raise PaymentError('refund total exceeds captured payment')
        r = PaymentRefund(tenant_id=tenant_id, payment_reference=payment_reference, refund_reference=refund_reference, amount=amount, currency=currency, reason=reason, status='requested')
        self.db.add(r); self.db.flush()
        self._event(tenant_id, 'payments.refund.requested', r.id, {'payment_reference': payment_reference, 'refund_reference': refund_reference, 'amount': str(amount), 'currency': currency})
        self.db.commit(); self.db.refresh(r); return r

    def complete_refund(self, tenant_id: int, refund_reference: str, *, provider_refund_id: str) -> PaymentRefund:
        r = self.db.scalar(select(PaymentRefund).where(PaymentRefund.tenant_id == tenant_id, PaymentRefund.refund_reference == refund_reference).with_for_update())
        if not r: raise PaymentError('refund not found')
        if r.status == 'succeeded':
            if r.provider_refund_id == provider_refund_id: return r
            raise PaymentError('refund is already completed')
        if r.status != 'requested': raise PaymentError('refund is not awaiting provider completion')
        if not provider_refund_id: raise PaymentError('provider refund id is required')
        conflict = self.db.scalar(select(PaymentRefund).where(PaymentRefund.tenant_id == tenant_id, PaymentRefund.provider_refund_id == provider_refund_id, PaymentRefund.id != r.id))
        if conflict: raise PaymentError('provider refund id already belongs to another refund')
        r.provider_refund_id = provider_refund_id; r.status='succeeded'; r.processed_at=datetime.now(timezone.utc)
        p = self._get(tenant_id, r.payment_reference, lock=True)
        total = sum((Decimal(str(x.amount)) for x in self.db.scalars(select(PaymentRefund).where(PaymentRefund.tenant_id==tenant_id, PaymentRefund.payment_reference==p.reference, PaymentRefund.status=='succeeded')).all()), Decimal('0'))
        if total == Decimal(str(p.amount)): p.status='refunded'; p.updated_at=datetime.now(timezone.utc)
        self._event(tenant_id, 'payments.refund.succeeded', r.id, {'payment_reference': p.reference, 'refund_reference': r.refund_reference, 'provider_refund_id': provider_refund_id, 'amount': str(r.amount), 'currency': r.currency})
        self.db.commit(); return r


    def reconcile(self, tenant_id: int, *, provider: str, provider_reference: str,
                  actual_amount: Decimal, currency: str, internal_reference: str | None = None) -> PaymentReconciliation:
        actual = Decimal(str(actual_amount))
        existing = self.db.scalar(select(PaymentReconciliation).where(
            PaymentReconciliation.tenant_id == tenant_id, PaymentReconciliation.provider == provider,
            PaymentReconciliation.provider_reference == provider_reference))
        if existing: return existing
        p = self.db.scalar(select(PaymentIntent).where(
            PaymentIntent.tenant_id == tenant_id, PaymentIntent.provider == provider,
            PaymentIntent.provider_payment_id == provider_reference))
        expected = Decimal(str(p.amount)) if p else None
        ref = internal_reference or (p.reference if p else None)
        if p is None: status = 'unknown'
        elif currency != p.currency: status = 'currency_mismatch'
        elif actual != expected: status = 'amount_mismatch'
        else: status = 'matched'
        r = PaymentReconciliation(tenant_id=tenant_id, provider=provider, provider_reference=provider_reference,
                                  internal_reference=ref, expected_amount=expected, actual_amount=actual,
                                  currency=currency, status=status,
                                  details_json=json.dumps({'expected_currency': p.currency if p else None}, sort_keys=True))
        self.db.add(r); self.db.flush()
        self._event(tenant_id, 'payments.reconciled', r.id,
                    {'provider': provider, 'provider_reference': provider_reference, 'status': status})
        self.db.commit(); self.db.refresh(r); return r
