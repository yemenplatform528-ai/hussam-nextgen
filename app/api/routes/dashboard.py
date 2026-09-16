from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from app.api.dependencies import get_context, get_session
from app.core.models.commerce import SalesOrder
from app.core.models.documents import BusinessDocument
from app.core.models.inventory import InventoryItem, Warehouse, InventoryMovementRecord, InventoryReservation
from app.core.models.logistics import Shipment
from app.core.models.payments import PaymentIntent
from app.core.models.procurement import PurchaseOrder
from app.core.models.core import Journal

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def count_for(db, model, tenant_id: int) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)) or 0)


@router.get("/summary")
def summary(ctx=Depends(get_context), db=Depends(get_session)):
    tenant_id = ctx.tenant_id
    sales = count_for(db, SalesOrder, tenant_id)
    purchases = count_for(db, PurchaseOrder, tenant_id)
    payments = count_for(db, PaymentIntent, tenant_id)
    shipments = count_for(db, Shipment, tenant_id)
    documents = count_for(db, BusinessDocument, tenant_id)
    items = count_for(db, InventoryItem, tenant_id)
    warehouses = count_for(db, Warehouse, tenant_id)
    journals = count_for(db, Journal, tenant_id)
    movements = count_for(db, InventoryMovementRecord, tenant_id)
    reservations = count_for(db, InventoryReservation, tenant_id)

    def statuses(model):
        rows = db.execute(
            select(model.status, func.count())
            .where(model.tenant_id == tenant_id)
            .group_by(model.status)
            .order_by(model.status)
        ).all()
        return {str(status): int(total) for status, total in rows}

    return {
        "tenant_id": tenant_id,
        "user_id": ctx.user_id,
        "membership_id": ctx.membership_id,
        "counts": {
            "items": items,
            "warehouses": warehouses,
            "inventory_movements": movements,
            "reservations": reservations,
            "sales_orders": sales,
            "purchase_orders": purchases,
            "payments": payments,
            "shipments": shipments,
            "documents": documents,
            "journals": journals,
        },
        "status": {
            "sales_orders": statuses(SalesOrder),
            "purchase_orders": statuses(PurchaseOrder),
            "payments": statuses(PaymentIntent),
            "shipments": statuses(Shipment),
            "documents": statuses(BusinessDocument),
        },
    }
