from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from app.api.dependencies import get_context, get_session
from app.core.models.inventory import InventoryItem, Warehouse, InventoryMovementRecord, InventoryReservation
from app.core.models.commerce import SalesOrder, SalesOrderLine
from app.core.models.procurement import Supplier, PurchaseOrder, PurchaseOrderLine, PurchaseReceipt, PurchaseReceiptLine
from app.core.models.payments import PaymentIntent, PaymentSettlement, PaymentReconciliation
from app.core.models.logistics import Shipment, ShipmentEvent, ShipmentCollection
from app.core.models.documents import BusinessDocument, DocumentVersion, DocumentLink
from app.core.models.core import Journal, JournalLineRecord

router = APIRouter(tags=["operations"])

def page(stmt, db, limit: int, offset: int):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()

def base(model, tenant_id):
    return select(model).where(model.tenant_id == tenant_id).order_by(desc(model.id))

@router.get("/products")
def products(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(InventoryItem, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"name":x.name,"unit_code":x.unit_code,"active":x.active} for x in rows],"limit":limit,"offset":offset}

@router.get("/warehouses")
def warehouses(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(Warehouse, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"name":x.name,"allow_negative_stock":x.allow_negative_stock,"active":x.active} for x in rows],"limit":limit,"offset":offset}

@router.get("/sales/orders")
def sales_orders(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(SalesOrder, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"reference":x.reference,"warehouse_id":x.warehouse_id,"currency":x.currency,"status":x.status,"total":str(x.total),"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}

@router.get("/purchasing/suppliers")
def suppliers(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(Supplier, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"name":x.name,"active":x.active} for x in rows],"limit":limit,"offset":offset}

@router.get("/purchasing/orders")
def purchase_orders(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(PurchaseOrder, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"reference":x.reference,"supplier_id":x.supplier_id,"warehouse_id":x.warehouse_id,"currency":x.currency,"status":x.status,"total":str(x.total),"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}

@router.get("/payments/intents")
def payment_intents(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(PaymentIntent, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"reference":x.reference,"provider":x.provider,"amount":str(x.amount),"currency":x.currency,"status":x.status,"provider_payment_id":x.provider_payment_id,"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}

@router.get("/logistics/shipments")
def shipments(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(Shipment, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"order_id":x.order_id,"reference":x.reference,"destination":x.destination,"carrier":x.carrier,"tracking_number":x.tracking_number,"status":x.status,"cod_amount":str(x.cod_amount),"currency":x.currency,"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}

@router.get("/finance/journals")
def journals(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(Journal, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"reference":x.reference,"currency":x.currency,"status":x.status,"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}

@router.get("/documents")
def documents(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(BusinessDocument, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"document_type":x.document_type,"reference":x.reference,"title":x.title,"status":x.status,"current_version":x.current_version,"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}

@router.get("/inventory/movements")
def movements(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = page(base(InventoryMovementRecord, ctx.tenant_id), db, limit, offset)
    return {"items":[{"id":x.id,"item_id":x.item_id,"warehouse_id":x.warehouse_id,"destination_warehouse_id":x.destination_warehouse_id,"quantity":str(x.quantity),"direction":x.direction,"reference":x.reference,"created_at":x.created_at.isoformat()} for x in rows],"limit":limit,"offset":offset}
