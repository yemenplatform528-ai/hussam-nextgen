from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.core.models import Journal, JournalLineRecord
from app.core.contracts import JournalCommand, JournalLine, StockMovement
from app.engines.identity import IdentityService, IdentityError
from app.engines.finance.persistence import FinancePersistenceService
from app.engines.finance.service import AccountingInvariantError
from app.engines.inventory.persistence import InventoryPersistenceService

def db():
    _, factory = make_session_factory(); return factory()

def test_identity_requires_active_membership():
    s=db(); ids=IdentityService(s); t=ids.create_tenant("متجر تجريبي"); u=ids.create_user("u1","u1@example.com")
    with pytest.raises(IdentityError): ids.authorize(u.id,t.id)
    ids.add_membership(u.id,t.id,"owner"); assert ids.authorize(u.id,t.id).role == "owner"

def test_finance_posts_atomically_and_is_tenant_scoped():
    s=db(); ids=IdentityService(s); t=ids.create_tenant("A")
    cmd=JournalCommand("SALE-1","YER",(JournalLine("cash",Decimal("100"),Decimal("0")),JournalLine("sales",Decimal("0"),Decimal("100"))))
    j=FinancePersistenceService(s).post(t.id,cmd); assert j.tenant_id==t.id and s.query(JournalLineRecord).count()==2
    with pytest.raises(AccountingInvariantError): FinancePersistenceService(s).post(t.id,cmd)

def test_inventory_records_movement_not_balance():
    s=db(); t=IdentityService(s).create_tenant("A")
    r=InventoryPersistenceService(s).record(t.id,StockMovement("item","wh",Decimal("5"),"in","GRN-1"))
    assert r.quantity == Decimal("5.0000")
