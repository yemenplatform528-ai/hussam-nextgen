from datetime import date
from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.core.contracts import JournalCommand,JournalLine,StockMovement
from app.engines.identity import IdentityService
from app.engines.finance.lifecycle import FinanceLifecycleService,FinanceLifecycleError
from app.engines.finance.accounts import create_account
from app.engines.inventory.persistence import InventoryPersistenceService
from app.engines.inventory.reservations import InventoryReservationService,ReservationError

def session(): return make_session_factory()[1]()
def cmd(ref='J1'): return JournalCommand(ref,'YER',(JournalLine('cash',Decimal('100'),Decimal('0')),JournalLine('sales',Decimal('0'),Decimal('100'))))
def test_closed_period_blocks_posting_and_reversal_is_separate():
 s=session(); t=IdentityService(s).create_tenant('A'); create_account(s,tenant_id=t.id,code='cash',name='Cash',account_type='asset',currency='YER'); create_account(s,tenant_id=t.id,code='sales',name='Sales',account_type='revenue',currency='YER'); f=FinanceLifecycleService(s); f.open_period(t.id,'2026',date(2026,1,1),date(2026,12,31)); j=f.post(t.id,cmd(),date(2026,9,1)); r=f.reverse(t.id,j.id,'REV-J1',date(2026,9,2)); assert r.id!=j.id
 f.close_period(t.id,1)
 with pytest.raises(FinanceLifecycleError): f.post(t.id,cmd('J2'),date(2026,9,2))
def test_finance_lifecycle_requires_posting_date():
 s=session(); t=IdentityService(s).create_tenant('A'); create_account(s,tenant_id=t.id,code='cash',name='Cash',account_type='asset',currency='YER'); create_account(s,tenant_id=t.id,code='sales',name='Sales',account_type='revenue',currency='YER'); f=FinanceLifecycleService(s); f.open_period(t.id,'2026',date(2026,1,1),date(2026,12,31))
 with pytest.raises(FinanceLifecycleError, match='posting date is required'): f.post(t.id,cmd())


def test_reservation_cannot_exceed_available_stock():
 s=session(); t=IdentityService(s).create_tenant('A'); InventoryPersistenceService(s).record(t.id,StockMovement('i','w',Decimal('5'),'in','IN-1')); rs=InventoryReservationService(s); rs.reserve(t.id,'i','w',Decimal('3'),'R1')
 with pytest.raises(ReservationError): rs.reserve(t.id,'i','w',Decimal('3'),'R2')
 rs.release(t.id,1); assert rs.reserve(t.id,'i','w',Decimal('3'),'R3').status=='active'
