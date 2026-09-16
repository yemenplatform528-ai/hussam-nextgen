from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.dependencies import get_context,get_session
from app.engines.commerce import CommerceProductionService,OrderLineInput
router=APIRouter(prefix="/sales",tags=["sales"])
class Line(BaseModel): item_id:str; quantity:Decimal=Field(gt=0); unit_price:Decimal=Field(ge=0)
class Draft(BaseModel): reference:str; warehouse_id:str; currency:str; lines:list[Line]=Field(min_length=1)
@router.post("/orders",status_code=201)
def create(body:Draft,ctx=Depends(get_context),db=Depends(get_session)):
    x=CommerceProductionService(db).create_draft(ctx.tenant_id,body.reference,body.warehouse_id,body.currency,[OrderLineInput(**v.model_dump()) for v in body.lines])
    return {"id":x.id,"reference":x.reference,"status":x.status,"total":str(x.total),"currency":x.currency}
@router.post("/orders/{order_id}/confirm")
def confirm(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=CommerceProductionService(db).confirm(ctx.tenant_id,order_id); return {"id":x.id,"status":x.status}
@router.post("/orders/{order_id}/fulfill")
def fulfill(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=CommerceProductionService(db).fulfill(ctx.tenant_id,order_id); return {"id":x.id,"status":x.status}
@router.post("/orders/{order_id}/cancel")
def cancel(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=CommerceProductionService(db).cancel(ctx.tenant_id,order_id); return {"id":x.id,"status":x.status}
