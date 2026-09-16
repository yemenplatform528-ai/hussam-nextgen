from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.core import Tenant, Journal, JournalLineRecord
from app.core.models.finance import FiscalPeriod
from app.engines.finance.accounts import create_account, deactivate_account
from app.engines.finance.production import PostingLine, post_journal
from app.engines.finance.reconciliation import trial_balance, ledger_totals, verify_journal_integrity, reconcile_control_account


def setup():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed(s):
    s.add(Tenant(name='Accounting', status='active')); s.flush()
    s.add(FiscalPeriod(tenant_id=1, name='2026', starts_on=date(2026,1,1), ends_on=date(2026,12,31), closed=False)); s.flush()


def test_chart_of_accounts_is_tenant_scoped_and_deactivatable():
    F = setup()
    with F() as s:
        seed(s)
        a = create_account(s, tenant_id=1, code='1000', name='Cash', account_type='asset', currency='YER')
        assert a.code == '1000' and a.active
        deactivate_account(s, tenant_id=1, code='1000')
        assert s.get(type(a), a.id).active is False


def test_posting_records_date_and_integrity_hash_and_trial_balance():
    F = setup()
    with F() as s:
        seed(s)
        j = post_journal(s, tenant_id=1, reference='SALE-1', currency='YER', posting_date=date(2026,9,13),
                         lines=[PostingLine('1000', debit=Decimal('125.50')), PostingLine('4000', credit=Decimal('125.50'))])
        assert j.posting_date == date(2026,9,13)
        assert j.content_hash and verify_journal_integrity(s, tenant_id=1, journal_id=j.id)
        tb = trial_balance(s, tenant_id=1, currency='YER')
        assert tb['1000']['debit'] == Decimal('125.5000')
        assert tb['4000']['credit'] == Decimal('125.5000')
        assert ledger_totals(s, tenant_id=1, currency='YER') == (Decimal('125.5000'), Decimal('125.5000'))


def test_integrity_detects_line_tampering_and_control_reconciliation():
    F = setup()
    with F() as s:
        seed(s)
        j = post_journal(s, tenant_id=1, reference='TAMPER-1', currency='YER', posting_date=date(2026,9,13),
                         lines=[PostingLine('1000', debit=Decimal('50')), PostingLine('4000', credit=Decimal('50'))])
        assert verify_journal_integrity(s, tenant_id=1, journal_id=j.id)
        line = s.query(JournalLineRecord).filter_by(journal_id=j.id, account='1000').one()
        line.debit = Decimal('51'); s.flush()
        assert not verify_journal_integrity(s, tenant_id=1, journal_id=j.id)
        assert reconcile_control_account(s, tenant_id=1, currency='YER', account_id='1000', expected_balance=Decimal('51'))['status'] == 'matched'
