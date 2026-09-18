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
from app.core.models.market import MarketContext, MarketCurrency, ProviderRegistryEntry, ProviderMarketCapability, PaymentRailRegistryEntry, PaymentAdapterRegistryEntry
import json


def db():
    _, factory = make_session_factory(); return factory()

def setup():
    s = db(); t = IdentityService(s).create_tenant('Payments Tenant')
    s.add(FiscalPeriod(tenant_id=t.id, name='2026', starts_on=date(2026,1,1), ends_on=date(2026,12,31), closed=False)); s.commit()
    return s, t, PaymentProductionService(s)


def governed_market(s, t, provider='wallet', currency='YER'):
    market = MarketContext(code='MKT-TEST', country_code='YE', name='Test Market', locale='en', timezone='UTC', default_currency=currency, status='active')
    s.add(market); s.flush(); s.add(MarketCurrency(market_id=market.id, currency=currency, is_default=True)); s.flush()
    evidence = json.dumps({k: True for k in __import__('app.engines.payment_adapters', fromlist=['REQUIRED_PRODUCTION_EVIDENCE']).REQUIRED_PRODUCTION_EVIDENCE})
    entry = ProviderRegistryEntry(code=provider, organization_name='Test Provider', provider_type='payment', product_name='Test Pay', status='production', integration_mode='api', metadata_json=evidence)
    s.add(entry); s.flush(); s.add_all([ProviderMarketCapability(provider_id=entry.id, market_id=market.id, capability='payment', currency=currency, active=True), ProviderMarketCapability(provider_id=entry.id, market_id=market.id, capability='settlement', currency=currency, active=True), ProviderMarketCapability(provider_id=entry.id, market_id=market.id, capability='refund', currency=currency, active=True)]); s.flush()
    rail = PaymentRailRegistryEntry(market_id=market.id, code='wallet', capability='payment', currency=currency, status='production')
    s.add(rail); s.flush(); s.add(PaymentAdapterRegistryEntry(provider_id=entry.id, rail_id=rail.id, adapter_code='test.wallet', adapter_version='1.0.0', status='production', active=True)); s.commit()
    return market

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
    s,t,p=setup(); m=governed_market(s,t); p.create_intent(t.id,'PAY-1','wallet',75,'YER',market_id=m.id); p.mark_processing(t.id,'PAY-1'); p.attach_provider_payment(t.id,'PAY-1','prov-1'); p.process_webhook(t.id,provider='wallet',event_id='e1',event_type='authorized',payment_reference='PAY-1',status='authorized'); p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    with pytest.raises(PaymentError,match='does not match'): p.settle(t.id,'PAY-1',settlement_reference='SET-1',actual_amount=74,currency='YER',posting_date=date(2026,9,10))
    s1=p.settle(t.id,'PAY-1',settlement_reference='SET-1',actual_amount=75,currency='YER',posting_date=date(2026,9,10))
    assert s1.status=='settled' and s.query(PaymentSettlement).count()==1
    assert s.query(Journal).filter_by(reference='SET:SET-1').count()==1
    same=p.settle(t.id,'PAY-1',settlement_reference='SET-1',actual_amount=75,currency='YER',posting_date=date(2026,9,10))
    assert same.id == s1.id and s.query(Journal).filter_by(reference='SET:SET-1').count()==1
    with pytest.raises(PaymentError,match='already has a settled'):
        p.settle(t.id,'PAY-1',settlement_reference='SET-2',actual_amount=75,currency='YER',posting_date=date(2026,9,10))

def test_reconciliation_detects_unknown_amount_and_currency_and_match():
    s,t,p=setup(); m=governed_market(s,t); p.create_intent(t.id,'PAY-1','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-1','prov-1')
    assert p.reconcile(t.id,provider='wallet',provider_reference='unknown',actual_amount=5,currency='YER',market_id=m.id).status=='unknown'
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-1',actual_amount=99,currency='YER',market_id=m.id).status=='amount_mismatch'
    # A distinct provider reference maps to a distinct intent only if attached.
    p.create_intent(t.id,'PAY-2','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-2','prov-2')
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-2',actual_amount=100,currency='SAR',market_id=m.id).status=='currency_mismatch'
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-1',actual_amount=99,currency='YER',market_id=m.id).status=='amount_mismatch'
    p.create_intent(t.id,'PAY-3','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-3','prov-3')
    assert p.reconcile(t.id,provider='wallet',provider_reference='prov-3',actual_amount=100,currency='YER',market_id=m.id).status=='matched'


def test_single_reconciliation_is_fail_closed_without_market_context():
    s,t,p=setup(); m=governed_market(s,t); p.create_intent(t.id,'PAY-RECON-GATE','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-RECON-GATE','prov-recon-gate')
    with pytest.raises(PaymentError, match='market context'):
        p.reconcile(t.id,provider='wallet',provider_reference='unknown-gate',actual_amount=5,currency='YER')
    with pytest.raises(PaymentError, match='does not match payment market'):
        p.reconcile(t.id,provider='wallet',provider_reference='prov-recon-gate',actual_amount=100,currency='YER',market_id=m.id + 999)

def test_payment_finance_failure_rolls_back_capture():
    s,t,p=setup(); p.create_intent(t.id,'PAY-1','wallet',30,'YER'); p.mark_processing(t.id,'PAY-1'); p.attach_provider_payment(t.id,'PAY-1','prov-1'); p.process_webhook(t.id,provider='wallet',event_id='e1',event_type='authorized',payment_reference='PAY-1',status='authorized')
    s.query(FiscalPeriod).filter_by(tenant_id=t.id).update({FiscalPeriod.closed: True}); s.commit()
    with pytest.raises(Exception): p.capture(t.id,'PAY-1',posting_date=date(2026,9,10))
    s.expire_all(); assert s.get(PaymentIntent,1).status=='authorized'; assert s.query(Journal).count()==0


def test_reconciliation_batch_is_fail_closed_and_idempotent():
    s,t,p=setup(); m=governed_market(s,t); p.create_intent(t.id,'PAY-1','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-1','prov-1')
    run=p.reconcile_batch(t.id,provider='wallet',market_id=m.id,currency='YER',run_reference='RUN-1',source_reference='statement-1',source_sha256='a'*64,
        rows=[{'provider_reference':'prov-1','actual_amount':100,'currency':'YER'}], expected_payment_references=['PAY-1'])
    assert run.status=='matched' and run.total_items==1 and run.matched_items==1 and run.exception_items==0
    same=p.reconcile_batch(t.id,provider='wallet',market_id=m.id,currency='YER',run_reference='RUN-1',source_reference='statement-1',source_sha256='a'*64,
        rows=[{'provider_reference':'prov-1','actual_amount':100,'currency':'YER'}], expected_payment_references=['PAY-1'])
    assert same.id==run.id
    closed=p.close_reconciliation_run(t.id,'RUN-1'); assert closed.status=='closed'
    assert p.close_reconciliation_run(t.id,'RUN-1').id==run.id


def test_reconciliation_batch_blocks_amount_currency_and_missing_internal_exceptions():
    s,t,p=setup(); m=governed_market(s,t); p.create_intent(t.id,'PAY-1','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-1','prov-1')
    run=p.reconcile_batch(t.id,provider='wallet',market_id=m.id,currency='YER',run_reference='RUN-2',source_reference='statement-2',source_sha256='b'*64,
        rows=[{'provider_reference':'prov-1','actual_amount':99,'currency':'YER'}, {'provider_reference':'unknown','actual_amount':5,'currency':'YER'}])
    assert run.status=='exceptions' and run.exception_items==2
    with pytest.raises(PaymentError,match='unresolved exceptions'): p.close_reconciliation_run(t.id,'RUN-2')


def test_settlement_requires_market_and_provider_capability_boundary():
    s,t,p=setup(); m=governed_market(s,t); payment=p.create_intent(t.id,'PAY-GATE','wallet',50,'YER',market_id=m.id); p.mark_processing(t.id,payment.reference); p.attach_provider_payment(t.id,payment.reference,'prov-gate'); p.process_webhook(t.id,provider='wallet',event_id='gate-e1',event_type='authorized',payment_reference=payment.reference,status='authorized'); p.capture(t.id,payment.reference,posting_date=date(2026,9,10))
    cap=s.query(ProviderMarketCapability).filter_by(market_id=m.id, capability='settlement').one(); cap.active=False; s.commit()
    with pytest.raises(PaymentError, match='provider production gate blocked'):
        p.settle(t.id,payment.reference,settlement_reference='SET-GATE',actual_amount=50,currency='YER',posting_date=date(2026,9,10))


def test_reconciliation_batch_rejects_cross_market_payment():
    s,t,p=setup(); m1=governed_market(s,t); m2=MarketContext(code='MKT-OTHER', country_code='SA', name='Other Market', locale='en', timezone='UTC', default_currency='SAR', status='active'); s.add(m2); s.flush(); s.add(MarketCurrency(market_id=m2.id,currency='SAR',is_default=True)); s.commit()
    payment=p.create_intent(t.id,'PAY-CROSS','wallet',100,'YER',market_id=m1.id); p.attach_provider_payment(t.id,payment.reference,'prov-cross')
    with pytest.raises(PaymentError):
        p.reconcile_batch(t.id,provider='wallet',market_id=m2.id,currency='SAR',run_reference='RUN-CROSS',source_reference='statement-cross',source_sha256='d'*64,rows=[{'provider_reference':'prov-cross','actual_amount':100,'currency':'SAR'}])


def test_reconciliation_batch_rejects_duplicate_provider_rows():
    s,t,p=setup(); m=governed_market(s,t); p.create_intent(t.id,'PAY-1','wallet',100,'YER',market_id=m.id); p.attach_provider_payment(t.id,'PAY-1','prov-1')
    with pytest.raises(PaymentError,match='duplicate provider reference'):
        p.reconcile_batch(t.id,provider='wallet',market_id=m.id,currency='YER',run_reference='RUN-3',source_reference='statement-3',source_sha256='c'*64,
            rows=[{'provider_reference':'prov-1','actual_amount':100,'currency':'YER'}, {'provider_reference':'prov-1','actual_amount':100,'currency':'YER'}])


def test_webhook_state_machine_blocks_unverified_capture_and_backward_moves():
    s,t,p=setup(); p.create_intent(t.id,'PAY-SM-1','wallet',50,'YER')
    with pytest.raises(PaymentError, match='invalid payment state transition'):
        p.process_webhook(t.id,provider='wallet',event_id='sm-1',event_type='captured',payment_reference='PAY-SM-1',status='captured')
    p.mark_processing(t.id,'PAY-SM-1'); p.attach_provider_payment(t.id,'PAY-SM-1','prov-sm-1')
    p.process_webhook(t.id,provider='wallet',event_id='sm-2',event_type='authorized',payment_reference='PAY-SM-1',status='authorized')
    p.process_webhook(t.id,provider='wallet',event_id='sm-3',event_type='captured',payment_reference='PAY-SM-1',status='captured')
    with pytest.raises(PaymentError, match='invalid payment state transition'):
        p.process_webhook(t.id,provider='wallet',event_id='sm-4',event_type='authorized',payment_reference='PAY-SM-1',status='authorized')


def test_webhook_terminal_states_cannot_reopen():
    s,t,p=setup(); p.create_intent(t.id,'PAY-SM-2','wallet',50,'YER'); p.mark_processing(t.id,'PAY-SM-2')
    p.process_webhook(t.id,provider='wallet',event_id='sm-5',event_type='failed',payment_reference='PAY-SM-2',status='failed')
    with pytest.raises(PaymentError, match='invalid payment state transition'):
        p.process_webhook(t.id,provider='wallet',event_id='sm-6',event_type='authorized',payment_reference='PAY-SM-2',status='authorized')

def test_settlement_tracks_reconciliation_state_and_closure_promotes_it():
    s,t,p=setup(); m=governed_market(s,t)
    payment=p.create_intent(t.id,'PAY-RECON-SET','wallet',100,'YER',market_id=m.id)
    p.attach_provider_payment(t.id,payment.reference,'prov-recon-set')
    settlement=p.settle(t.id,payment.reference,settlement_reference='SET-RECON-SET',actual_amount=100,currency='YER',posting_date=date(2026,9,10)) if False else None
    # Settlement requires captured state; drive the normal lifecycle first.
    p.mark_processing(t.id,payment.reference)
    p.process_webhook(t.id,provider='wallet',event_id='recon-set-e1',event_type='authorized',payment_reference=payment.reference,status='authorized')
    p.capture(t.id,payment.reference,posting_date=date(2026,9,10))
    settlement=p.settle(t.id,payment.reference,settlement_reference='SET-RECON-SET',actual_amount=100,currency='YER',posting_date=date(2026,9,10))
    assert settlement.reconciliation_status == 'pending'
    run=p.reconcile_batch(t.id,provider='wallet',market_id=m.id,currency='YER',run_reference='RUN-RECON-SET',source_reference='statement-recon-set',source_sha256='e'*64,
        rows=[{'provider_reference':'prov-recon-set','actual_amount':100,'currency':'YER'}])
    assert run.status == 'matched'
    closed=p.close_reconciliation_run(t.id,'RUN-RECON-SET')
    assert closed.status == 'closed'
    s.refresh(settlement)
    assert settlement.reconciliation_status == 'reconciled'
    assert settlement.reconciliation_run_reference == 'RUN-RECON-SET'


def test_settlement_created_after_closed_reconciliation_is_already_reconciled():
    s,t,p=setup(); m=governed_market(s,t)
    payment=p.create_intent(t.id,'PAY-RECON-FIRST','wallet',50,'YER',market_id=m.id)
    p.attach_provider_payment(t.id,payment.reference,'prov-recon-first')
    run=p.reconcile_batch(t.id,provider='wallet',market_id=m.id,currency='YER',run_reference='RUN-RECON-FIRST',source_reference='statement-recon-first',source_sha256='f'*64,
        rows=[{'provider_reference':'prov-recon-first','actual_amount':50,'currency':'YER'}])
    assert run.status == 'matched'
    p.close_reconciliation_run(t.id,'RUN-RECON-FIRST')
    p.mark_processing(t.id,payment.reference)
    p.process_webhook(t.id,provider='wallet',event_id='recon-first-e1',event_type='authorized',payment_reference=payment.reference,status='authorized')
    p.capture(t.id,payment.reference,posting_date=date(2026,9,10))
    settlement=p.settle(t.id,payment.reference,settlement_reference='SET-RECON-FIRST',actual_amount=50,currency='YER',posting_date=date(2026,9,10))
    assert settlement.reconciliation_status == 'reconciled'
    assert settlement.reconciliation_run_reference == 'RUN-RECON-FIRST'
