from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.persistence import Base
from app.core.models.core import Tenant, Journal, JournalLineRecord
from app.core.models.finance import FiscalPeriod
from app.engines.finance.production import FinanceError, PostingLine, post_journal, reverse_journal
from app.engines.finance.reconciliation import account_balance

def setup():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

def seed_period(s, tenant_id=1, closed=False):
    s.add(FiscalPeriod(
        tenant_id=tenant_id,
        name=f"period-{tenant_id}-{closed}",
        starts_on=date(2026,1,1),
        ends_on=date(2026,12,31),
        closed=closed,
    ))
    s.flush()

def test_posting_requires_open_period_and_balances():
    F=setup()
    with F() as s:
        s.add(Tenant(name="T",status="active")); s.flush(); seed_period(s)
        j=post_journal(s,tenant_id=1,reference="J-1",currency="YER",
            posting_date=date(2026,8,1),
            lines=[PostingLine("10",debit=Decimal("100.25")),
                   PostingLine("20",credit=Decimal("100.25"))])
        assert j.id
        assert account_balance(s,tenant_id=1,account_id="10",currency="YER")==Decimal("100.25")
        with pytest.raises(FinanceError):
            post_journal(s,tenant_id=1,reference="J-2",currency="YER",
                posting_date=date(2027,1,1),
                lines=[PostingLine("10",debit=1),PostingLine("20",credit=1)])

def test_invalid_lines_are_rejected():
    F=setup()
    with F() as s:
        s.add(Tenant(name="T",status="active")); s.flush(); seed_period(s)
        with pytest.raises(FinanceError):
            post_journal(s,tenant_id=1,reference="BAD",currency="YER",
                posting_date=date(2026,2,1),
                lines=[PostingLine("1",debit=10,credit=1),PostingLine("2",credit=9)])

def test_closed_period_blocks_posting():
    F=setup()
    with F() as s:
        s.add(Tenant(name="T",status="active")); s.flush(); seed_period(s,closed=True)
        with pytest.raises(FinanceError):
            post_journal(s,tenant_id=1,reference="CLOSED",currency="YER",
                posting_date=date(2026,2,1),
                lines=[PostingLine("1",debit=5),PostingLine("2",credit=5)])

def test_reversal_is_new_journal_and_preserves_original():
    F=setup()
    with F() as s:
        s.add(Tenant(name="T",status="active")); s.flush(); seed_period(s)
        original=post_journal(s,tenant_id=1,reference="SALE-1",currency="YER",
            posting_date=date(2026,3,1),
            lines=[PostingLine("1",debit=50),PostingLine("2",credit=50)])
        reversal=reverse_journal(s,tenant_id=1,journal_id=original.id,
            reversal_reference="REV-1",reversal_date=date(2026,3,2))
        assert reversal.id != original.id
        assert s.get(Journal,original.id).reference=="SALE-1"
        lines=s.query(JournalLineRecord).filter_by(journal_id=reversal.id).all()
        assert {str(x.account): (Decimal(x.debit),Decimal(x.credit)) for x in lines} == {
            "1":(Decimal("0"),Decimal("50")),"2":(Decimal("50"),Decimal("0"))}

def test_cross_tenant_reversal_is_rejected():
    F=setup()
    with F() as s:
        s.add_all([Tenant(name="A",status="active"),Tenant(name="B",status="active")]); s.flush()
        seed_period(s,1); seed_period(s,2)
        original=post_journal(s,tenant_id=1,reference="A-1",currency="YER",
            posting_date=date(2026,4,1),
            lines=[PostingLine("1",debit=10),PostingLine("2",credit=10)])
        with pytest.raises(FinanceError):
            reverse_journal(s,tenant_id=2,journal_id=original.id,
                reversal_reference="B-REV",reversal_date=date(2026,4,2))

def test_duplicate_reference_is_tenant_local():
    F=setup()
    with F() as s:
        s.add_all([Tenant(name="A",status="active"),Tenant(name="B",status="active")]); s.flush()
        seed_period(s,1); seed_period(s,2)
        args=dict(currency="YER",posting_date=date(2026,5,1),
                  lines=[PostingLine("1",debit=7),PostingLine("2",credit=7)])
        post_journal(s,tenant_id=1,reference="R",**args)
        with pytest.raises(FinanceError): post_journal(s,tenant_id=1,reference="R",**args)
        assert post_journal(s,tenant_id=2,reference="R",**args).id
