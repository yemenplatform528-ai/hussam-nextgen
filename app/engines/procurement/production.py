from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.inventory import InventoryItem, Warehouse, InventoryMovementRecord
from app.core.models.procurement import Supplier, PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from app.core.models.governance import OutboxEvent
from app.engines.finance.production import PostingLine, post_journal

class ProcurementError(ValueError): pass

@dataclass(frozen=True)
class PurchaseLineInput:
    item_id: str
    quantity: Decimal
    unit_cost: Decimal

@dataclass(frozen=True)
class ReceiptLineInput:
    purchase_order_line_id: int
    quantity: Decimal

def _positive(v, label):
    v=Decimal(str(v))
    if v<=0: raise ProcurementError(f'{label} must be positive')
    return v

def _nonnegative(v, label):
    v=Decimal(str(v))
    if v<0: raise ProcurementError(f'{label} must be non-negative')
    return v

class ProcurementProductionService:
    def __init__(self, db: Session): self.db=db

    def _supplier(self, tenant_id, supplier_id):
        x=self.db.scalar(select(Supplier).where(Supplier.tenant_id==tenant_id,Supplier.id==supplier_id,Supplier.active.is_(True)))
        if x is None: raise ProcurementError('supplier not found in tenant')
        return x
    def _warehouse(self, tenant_id, warehouse_id):
        x=self.db.scalar(select(Warehouse).where(Warehouse.tenant_id==tenant_id,Warehouse.id==warehouse_id,Warehouse.active.is_(True)))
        if x is None: raise ProcurementError('warehouse not found in tenant')
        return x
    def _item(self, tenant_id, item_id):
        x=self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id==tenant_id,InventoryItem.id==item_id,InventoryItem.active.is_(True)))
        if x is None: raise ProcurementError('item not found in tenant')
        return x
    def _event(self, tenant_id, event_type, aggregate_id, payload):
        from uuid import uuid4
        self.db.add(OutboxEvent(event_id=str(uuid4()),tenant_id=tenant_id,event_type=event_type,aggregate_type='purchase_order',aggregate_id=str(aggregate_id),payload=payload,published=False))

    def create_supplier(self, tenant_id, supplier_id, name):
        if not supplier_id or not name: raise ProcurementError('supplier id and name are required')
        if self.db.scalar(select(Supplier).where(Supplier.tenant_id==tenant_id,Supplier.id==supplier_id)): raise ProcurementError('supplier already exists in tenant')
        x=Supplier(id=supplier_id,tenant_id=tenant_id,name=name,active=True); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

    def create_draft(self, tenant_id, reference, supplier_id, warehouse_id, currency, lines):
        if not reference or not currency or not lines: raise ProcurementError('reference, currency and at least one line are required')
        self._supplier(tenant_id,supplier_id); self._warehouse(tenant_id,warehouse_id)
        if self.db.scalar(select(PurchaseOrder).where(PurchaseOrder.tenant_id==tenant_id,PurchaseOrder.reference==reference)): raise ProcurementError('duplicate purchase order reference')
        o=PurchaseOrder(tenant_id=tenant_id,supplier_id=supplier_id,warehouse_id=warehouse_id,reference=reference,currency=currency,status='draft',total=Decimal('0')); self.db.add(o); self.db.flush()
        total=Decimal('0')
        for data in lines:
            item=self._item(tenant_id,data.item_id); q=_positive(data.quantity,'quantity'); c=_nonnegative(data.unit_cost,'unit cost'); lt=q*c; total+=lt
            self.db.add(PurchaseOrderLine(order_id=o.id,tenant_id=tenant_id,item_id=item.id,quantity=q,unit_cost=c,received_quantity=Decimal('0'),line_total=lt))
        o.total=total; self._event(tenant_id,'procurement.purchase_order.created',o.id,{'reference':reference,'total':str(total),'currency':currency})
        try: self.db.commit(); self.db.refresh(o); return o
        except IntegrityError: self.db.rollback(); raise ProcurementError('duplicate purchase order reference')

    def confirm(self, tenant_id, order_id):
        o=self.db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==order_id,PurchaseOrder.tenant_id==tenant_id))
        if o is None: raise ProcurementError('purchase order not found in tenant')
        if o.status!='draft': raise ProcurementError('only draft purchase orders can be confirmed')
        self._supplier(tenant_id,o.supplier_id); self._warehouse(tenant_id,o.warehouse_id)
        if not self.db.scalar(select(PurchaseOrderLine).where(PurchaseOrderLine.order_id==o.id,PurchaseOrderLine.tenant_id==tenant_id)): raise ProcurementError('purchase order has no lines')
        o.status='confirmed'; self._event(tenant_id,'procurement.purchase_order.confirmed',o.id,{'reference':o.reference}); self.db.commit(); return o

    def cancel(self, tenant_id, order_id):
        o=self.db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==order_id,PurchaseOrder.tenant_id==tenant_id))
        if o is None: raise ProcurementError('purchase order not found in tenant')
        if o.status not in ('draft','confirmed'): raise ProcurementError('purchase order cannot be cancelled in its current status')
        o.status='cancelled'; self._event(tenant_id,'procurement.purchase_order.cancelled',o.id,{'reference':o.reference}); self.db.commit(); return o

    def receive(self, tenant_id, order_id, reference, lines, *, posting_date: date|None=None, post_accounting=False, inventory_account='inventory', payable_account='accounts_payable', actor_id=None):
        try:
            o=self.db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==order_id,PurchaseOrder.tenant_id==tenant_id).with_for_update())
            if o is None: raise ProcurementError('purchase order not found in tenant')
            if o.status not in ('confirmed','partially_received'): raise ProcurementError('purchase order is not receivable')
            if not reference or not lines: raise ProcurementError('receipt reference and lines are required')
            self._warehouse(tenant_id,o.warehouse_id)
            if self.db.scalar(select(PurchaseReceipt).where(PurchaseReceipt.tenant_id==tenant_id,PurchaseReceipt.reference==reference)): raise ProcurementError('duplicate receipt reference')
            order_lines={x.id:x for x in self.db.scalars(select(PurchaseOrderLine).where(PurchaseOrderLine.order_id==o.id,PurchaseOrderLine.tenant_id==tenant_id).with_for_update()).all()}
            if not order_lines: raise ProcurementError('purchase order has no lines')
            normalized=[]; seen=set(); total=Decimal('0')
            for data in lines:
                if data.purchase_order_line_id in seen: raise ProcurementError('duplicate receipt line')
                seen.add(data.purchase_order_line_id)
                line=order_lines.get(data.purchase_order_line_id)
                if line is None: raise ProcurementError('purchase order line not found in tenant/order')
                q=_positive(data.quantity,'receipt quantity'); remaining=Decimal(str(line.quantity))-Decimal(str(line.received_quantity))
                if q>remaining: raise ProcurementError('receipt quantity exceeds remaining ordered quantity')
                lt=q*Decimal(str(line.unit_cost)); total+=lt; normalized.append((line,q,lt))
            if post_accounting and posting_date is None: raise ProcurementError('posting date is required for accounting')
            receipt=PurchaseReceipt(tenant_id=tenant_id,purchase_order_id=o.id,reference=reference,currency=o.currency,status='posted',total=total); self.db.add(receipt); self.db.flush()
            for line,q,lt in normalized:
                self.db.add(PurchaseReceiptLine(receipt_id=receipt.id,tenant_id=tenant_id,purchase_order_line_id=line.id,item_id=line.item_id,quantity=q,unit_cost=line.unit_cost,line_total=lt))
                self.db.add(InventoryMovementRecord(tenant_id=tenant_id,item_id=line.item_id,warehouse_id=o.warehouse_id,quantity=q,direction='in',reference=f'receipt:{reference}:line:{line.id}'))
                line.received_quantity=Decimal(str(line.received_quantity))+q
            states=[Decimal(str(x.received_quantity)) < Decimal(str(x.quantity)) for x in order_lines.values()]
            o.status='partially_received' if any(states) else 'received'
            if post_accounting:
                post_journal(self.db,tenant_id=tenant_id,reference=f'GRN:{reference}',currency=o.currency,posting_date=posting_date,actor_id=actor_id,lines=[PostingLine(inventory_account,debit=total),PostingLine(payable_account,credit=total)])
            self._event(tenant_id,'procurement.purchase_receipt.posted',receipt.id,{'reference':reference,'order_reference':o.reference,'total':str(total),'currency':o.currency,'accounting_posted':post_accounting})
            self.db.commit(); self.db.refresh(receipt); return receipt
        except IntegrityError:
            self.db.rollback(); raise ProcurementError('receipt conflicts with existing reference or movement')
        except Exception:
            self.db.rollback(); raise
