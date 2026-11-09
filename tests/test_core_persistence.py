from datetime import date
from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.core.models import Journal, JournalLineRecord
from app.core.models.finance import FiscalPeriod
from app.core.contracts import JournalCommand, JournalLine, StockMovement
from app.engines.identity import IdentityService, IdentityError
from app.engines.finance.persistence import FinancePersistenceService
from app.engines.finance.service import AccountingInvariantError
from app.engines.finance.accounts import create_account
from app.engines.inventory.persistence import InventoryPersistenceService

def db():
    _, factory = make_session_factory(); return factory()

def test_identity_requires_active_membership():
    s=db(); ids=IdentityService(s); t=ids.create_tenant("متجر تجريبي"); u=ids.create_user("u1","u1@example.com")
    with pytest.raises(IdentityError): ids.authorize(u.id,t.id)
    ids.add_membership(u.id,t.id,"owner"); assert ids.authorize(u.id,t.id).role == "owner"

def test_finance_posts_atomically_and_is_tenant_scoped():
    s=db(); ids=IdentityService(s); t=ids.create_tenant("A")
    create_account(s, tenant_id=t.id, code="cash", name="Cash", account_type="asset", currency="YER")
    create_account(s, tenant_id=t.id, code="sales", name="Sales", account_type="revenue", currency="YER")
    s.add(FiscalPeriod(tenant_id=t.id, name="2026", starts_on=date(2026,1,1), ends_on=date(2026,12,31), closed=False))
    s.flush()
    cmd=JournalCommand("SALE-1","YER",(JournalLine("cash",Decimal("100"),Decimal("0")),JournalLine("sales",Decimal("0"),Decimal("100"))), posting_date=date(2026,9,25))
    j=FinancePersistenceService(s).post(t.id,cmd); assert j.tenant_id==t.id and s.query(JournalLineRecord).count()==2
    with pytest.raises(AccountingInvariantError): FinancePersistenceService(s).post(t.id,cmd)

def test_finance_persistence_rejects_accounts_outside_tenant_chart():
    s=db(); ids=IdentityService(s); t=ids.create_tenant("A")
    cmd=JournalCommand("MISSING-ACCOUNT","YER",(JournalLine("cash",Decimal("1"),Decimal("0")),JournalLine("sales",Decimal("0"),Decimal("1"))), posting_date=date(2026,9,25))
    with pytest.raises(AccountingInvariantError, match="not found in tenant"):
        FinancePersistenceService(s).post(t.id,cmd)


def test_finance_persistence_requires_posting_date():
    s=db(); ids=IdentityService(s); t=ids.create_tenant("A")
    create_account(s, tenant_id=t.id, code="cash", name="Cash", account_type="asset", currency="YER")
    create_account(s, tenant_id=t.id, code="sales", name="Sales", account_type="revenue", currency="YER")
    cmd=JournalCommand("NO-POSTING-DATE","YER",(JournalLine("cash",Decimal("1"),Decimal("0")),JournalLine("sales",Decimal("0"),Decimal("1"))))
    with pytest.raises(AccountingInvariantError, match="posting date is required"):
        FinancePersistenceService(s).post(t.id,cmd)


def test_inventory_records_movement_not_balance():
    s=db(); t=IdentityService(s).create_tenant("A")
    r=InventoryPersistenceService(s).record(t.id,StockMovement("item","wh",Decimal("5"),"in","GRN-1"))
    assert r.quantity == Decimal("5.0000")
