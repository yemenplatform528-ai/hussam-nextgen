from datetime import date
from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.engines.identity import IdentityService
from app.engines.payments import PaymentProductionService, PaymentError
from app.core.models.payments import PaymentIntent, PaymentWebhook, PaymentSettlement, PaymentReconciliation
from app.core.models.finance import FiscalPeriod
from app.core.models.core import Journal, JournalLineRecord
from app.core.models.governance import OutboxEvent


def db():
    _, factory = make_session_factory(); return factory()

def setup():
    s = db(); t = IdentityService(s).create_tenant('Payments Tenant')
    s.add(FiscalPeriod(tenant_id=t.id, name='2026', starts_on=date(2026,1,1), ends_on=date(2026,12,31), closed=False)); s.commit()
    return s, t, PaymentProductionService(s)

def test_create_and_webhook_are_tenant_scoped_and_idempotent():
    s,t,p=setup(); x=p.create_intent(t.id,'PAY-1','wallet',Decimal('100.25'),'YER')
    p.mark_processing(t.id,'PAY-1'); p.attach_provider_payment(t.id,'PAY-1','prov-1')
    h=p.process_webhook(t.id,provider='wallet',event_id='evt-1',event_type='authorized',payment_reference='PAY-1',status='authorized',payload={'ok':True})
    assert h.processed is True and s.get(PaymentIntent,x.id).status=='authorized'
    same=p.process_webhook(t.id,provider='wallet',event_id='evt-1',event_type='authorized',payment_reference='PAY-1',status='authorized')
    assert same.id==h.id and s.query(PaymentWebhook).count()==1

def test_webhook_provider_and_tenant_mismatch_rejected():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',10,'YER')
    t2=IdentityService(s).create_tenant('Other')
    with pytest.raises(PaymentError): p.process_webhook(t.id,provider='bank',event_id='e',event_type='authorized',payment_reference='PAY-1',status='authorized')
    with pytest.raises(PaymentError,match='not found'): p.process_webhook(t2.id,provider='wallet',event_id='e',event_type='authorized',payment_reference='PAY-1',status='authorized')

def test_capture_requires_verified_provider_payment_and_posts_clearing_journal():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',Decimal('250.00'),'YER'); p.mark_processing(t.id,'PAY-1')
    with pytest.raises(PaymentError,match='verified'): p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    p.attach_provider_payment(t.id,'PAY-1','prov-1'); p.process_webhook(t.id,provider='wallet',event_id='e1',event_type='authorized',payment_reference='PAY-1',status='authorized')
    x=p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    assert x.status=='captured'
    j=s.query(Journal).filter_by(reference='PAY:PAY-1:capture').one(); ls=s.query(JournalLineRecord).filter_by(journal_id=j.id).all()
    assert sum((Decimal(str(z.debit)) for z in ls),Decimal('0'))==Decimal('250.00')
    assert sum((Decimal(str(z.credit)) for z in ls),Decimal('0'))==Decimal('250.00')

def test_capture_is_not_repeatable():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',20,'YER'); p.mark_processing(t.id,'PAY-1'); p.attach_provider_payment(t.id,'PAY-1','prov-1'); p.process_webhook(t.id,provider='wallet',event_id='e1',event_type='authorized',payment_reference='PAY-1',status='authorized'); p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    with pytest.raises(PaymentError): p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))

def test_settlement_requires_exact_amount_and_moves_clearing_to_cash():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',75,'YER'); p.mark_processing(t.id,'PAY-1'); p.attach_provider_payment(t.id,'PAY-1','prov-1'); p.process_webhook(t.id,provider='wallet',event_id='e1',event_type='authorized',payment_reference='PAY-1',status='authorized'); p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    with pytest.raises(PaymentError,match='does not match'): p.settle(t.id,'PAY-1',settlement_reference='SET-1',actual_amount=74,currency='YER',posting_date=date(2026,9,10))
    s1=p.settle(t.id,'PAY-1',settlement_reference='SET-1',actual_amount=75,currency='YER',posting_date=date(2026,9,10))
    assert s1.status=='settled' and s.query(PaymentSettlement).count()==1
    assert s.query(Journal).filter_by(reference='SET:SET-1').count()==1

def test_reconciliation_detects_unknown_amount_and_currency_and_match():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',100,'YER'); p.attach_provider_payment(t.id,'PAY-1','prov-1')
    assert p.reconcile(t.id,provider='wallet',provider_reference='unknown',actual_amount=5,currency='YER').status=='unknown'
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-1',actual_amount=99,currency='YER').status=='amount_mismatch'
    # A distinct provider reference maps to a distinct intent only if attached.
    p.create_intent(t.id,'PAY-2','wallet',100,'YER'); p.attach_provider_payment(t.id,'PAY-2','prov-2')
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-2',actual_amount=100,currency='SAR').status=='currency_mismatch'
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-1',actual_amount=99,currency='YER').status=='amount_mismatch'
    p.create_intent(t.id,'PAY-3','wallet',100,'YER'); p.attach_provider_payment(t.id,'PAY-3','prov-3')
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-3',actual_amount=100,currency='YER').status=='matched'

def test_payment_finance_failure_rolls_back_capture():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',30,'YER'); p.mark_processing(t.id,'PAY-1'); p.attach_provider_payment(t.id,'PAY-1','prov-1'); p.process_webhook(t.id,provider='wallet',event_id='e1',event_type='authorized',payment_reference='PAY-1',status='authorized')
    s.query(FiscalPeriod).filter_by(tenant_id=t.id).update({FiscalPeriod.closed: True}); s.commit()
    with pytest.raises(Exception): p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    s.expire_all(); assert s.get(PaymentIntent,1).status=='authorized'; assert s.query(Journal).count()==0
