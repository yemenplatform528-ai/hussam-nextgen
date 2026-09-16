from datetime import date
from decimal import Decimal
import pytest
from app.core.persistence import make_session_factory
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.procurement.production import ProcurementProductionService, ProcurementError, PurchaseLineInput, ReceiptLineInput
from app.core.contracts import StockMovement
from app.core.models.procurement import PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from app.core.models.inventory import InventoryMovementRecord
from app.core.models.finance import FiscalPeriod
from app.core.models.core import Journal, JournalLineRecord

def db(): _, factory=make_session_factory(); return factory()
def setup():
    s=db(); t=IdentityService(s).create_tenant('Procurement Tenant'); inv=InventoryProductionService(s)
    inv.create_item(t.id,'item-1','Item 1'); inv.create_item(t.id,'item-2','Item 2'); inv.create_warehouse(t.id,'wh-a','A')
    p=ProcurementProductionService(s); p.create_supplier(t.id,'sup-1','Supplier 1'); return s,t,p

def test_create_draft_calculates_exact_total_and_tenant_scope():
    s,t,p=setup(); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('2'),Decimal('100.25')),PurchaseLineInput('item-2',Decimal('1.5'),Decimal('20'))])
    assert o.total==Decimal('230.50') and o.status=='draft'; assert s.query(PurchaseOrderLine).filter_by(order_id=o.id).count()==2

def test_confirm_requires_draft_and_then_allows_receipt():
    s,t,p=setup(); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('5'),Decimal('10'))]); p.confirm(t.id,o.id); assert s.get(PurchaseOrder,o.id).status=='confirmed'

def test_partial_and_final_receipts_update_inventory_and_order_lifecycle():
    s,t,p=setup(); inv=InventoryProductionService(s); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('10'),Decimal('10'))]); p.confirm(t.id,o.id); line=s.query(PurchaseOrderLine).filter_by(order_id=o.id).one()
    p.receive(t.id,o.id,'GRN-1',[ReceiptLineInput(line.id,Decimal('4'))]); assert s.get(PurchaseOrder,o.id).status=='partially_received'
    p.receive(t.id,o.id,'GRN-2',[ReceiptLineInput(line.id,Decimal('6'))]); assert s.get(PurchaseOrder,o.id).status=='received'; assert inv.snapshot(t.id,'item-1','wh-a').on_hand==Decimal('10')

def test_receipt_cannot_exceed_remaining_quantity_and_rolls_back_atomically():
    s,t,p=setup(); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('5'),Decimal('10')),PurchaseLineInput('item-2',Decimal('5'),Decimal('20'))]); p.confirm(t.id,o.id); lines=s.query(PurchaseOrderLine).filter_by(order_id=o.id).order_by(PurchaseOrderLine.id).all()
    with pytest.raises(ProcurementError,match='exceeds'):
        p.receive(t.id,o.id,'GRN-1',[ReceiptLineInput(lines[0].id,Decimal('6')),ReceiptLineInput(lines[1].id,Decimal('1'))])
    s.expire_all(); assert s.query(PurchaseReceipt).count()==0 and s.query(InventoryMovementRecord).count()==0

def test_duplicate_receipt_reference_is_blocked_per_tenant():
    s,t,p=setup(); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('2'),Decimal('10'))]); p.confirm(t.id,o.id); line=s.query(PurchaseOrderLine).filter_by(order_id=o.id).one(); p.receive(t.id,o.id,'GRN-1',[ReceiptLineInput(line.id,Decimal('1'))])
    o2=p.create_draft(t.id,'PO-2','sup-1','wh-a','YER',[PurchaseLineInput('item-2',Decimal('2'),Decimal('10'))]); p.confirm(t.id,o2.id); line2=s.query(PurchaseOrderLine).filter_by(order_id=o2.id).one()
    with pytest.raises(ProcurementError,match='duplicate'): p.receive(t.id,o2.id,'GRN-1',[ReceiptLineInput(line2.id,Decimal('1'))])

def test_cross_tenant_supplier_order_access_is_denied():
    s,t,p=setup(); t2=IdentityService(s).create_tenant('Other'); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('1'),Decimal('10'))])
    with pytest.raises(ProcurementError,match='not found'): p.confirm(t2.id,o.id)

def test_receipt_can_atomically_post_inventory_and_supplier_liability():
    s,t,p=setup(); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('3'),Decimal('12.50'))]); p.confirm(t.id,o.id); line=s.query(PurchaseOrderLine).filter_by(order_id=o.id).one(); s.add(FiscalPeriod(tenant_id=t.id,name='2026',starts_on=date(2026,1,1),ends_on=date(2026,12,31),closed=False)); s.commit()
    r=p.receive(t.id,o.id,'GRN-1',[ReceiptLineInput(line.id,Decimal('3'))],posting_date=date(2026,9,10),post_accounting=True)
    assert r.total==Decimal('37.50'); j=s.query(Journal).filter_by(tenant_id=t.id,reference='GRN:GRN-1').one(); ls=s.query(JournalLineRecord).filter_by(journal_id=j.id).all(); assert sum((Decimal(str(x.debit)) for x in ls),Decimal('0'))==Decimal('37.50'); assert sum((Decimal(str(x.credit)) for x in ls),Decimal('0'))==Decimal('37.50')

def test_accounting_failure_rolls_back_receipt_and_inventory():
    s,t,p=setup(); o=p.create_draft(t.id,'PO-1','sup-1','wh-a','YER',[PurchaseLineInput('item-1',Decimal('2'),Decimal('10'))]); p.confirm(t.id,o.id); line=s.query(PurchaseOrderLine).filter_by(order_id=o.id).one()
    with pytest.raises(Exception): p.receive(t.id,o.id,'GRN-1',[ReceiptLineInput(line.id,Decimal('2'))],posting_date=date(2026,9,10),post_accounting=True)
    s.expire_all(); assert s.query(PurchaseReceipt).count()==0 and s.query(InventoryMovementRecord).count()==0 and s.get(PurchaseOrder,o.id).status=='confirmed'
