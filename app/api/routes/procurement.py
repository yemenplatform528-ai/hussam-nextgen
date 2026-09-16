from decimal import Decimal
from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field
from app.api.dependencies import get_context,get_session
from app.engines.procurement.production import ProcurementProductionService,PurchaseLineInput,ReceiptLineInput
router=APIRouter(prefix="/purchasing",tags=["purchasing"])
class SupplierIn(BaseModel): id:str; name:str
class Line(BaseModel): item_id:str; quantity:Decimal=Field(gt=0); unit_cost:Decimal=Field(ge=0)
class Draft(BaseModel): reference:str;supplier_id:str;warehouse_id:str;currency:str;lines:list[Line]=Field(min_length=1)
class ReceiptLine(BaseModel): purchase_order_line_id:int;quantity:Decimal=Field(gt=0)
class Receipt(BaseModel): reference:str;lines:list[ReceiptLine]=Field(min_length=1);posting_date:str|None=None;post_accounting:bool=False
@router.post("/suppliers",status_code=201)
def supplier(body:SupplierIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=ProcurementProductionService(db).create_supplier(ctx.tenant_id,body.id,body.name);return {"id":x.id,"name":x.name}
@router.post("/orders",status_code=201)
def create(body:Draft,ctx=Depends(get_context),db=Depends(get_session)):
    x=ProcurementProductionService(db).create_draft(ctx.tenant_id,body.reference,body.supplier_id,body.warehouse_id,body.currency,[PurchaseLineInput(**v.model_dump()) for v in body.lines]);return {"id":x.id,"reference":x.reference,"status":x.status,"total":str(x.total)}
@router.post("/orders/{order_id}/confirm")
def confirm(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=ProcurementProductionService(db).confirm(ctx.tenant_id,order_id);return {"id":x.id,"status":x.status}

@router.post("/orders/{order_id}/receive",status_code=201)
def receive(order_id:int,body:Receipt,ctx=Depends(get_context),db=Depends(get_session)):
    from datetime import date
    x=ProcurementProductionService(db).receive(ctx.tenant_id, order_id, body.reference, [ReceiptLineInput(**v.model_dump()) for v in body.lines], posting_date=date.fromisoformat(body.posting_date) if body.posting_date else None, post_accounting=body.post_accounting, actor_id=ctx.user_id); return {"id":x.id,"reference":x.reference,"status":x.status}
