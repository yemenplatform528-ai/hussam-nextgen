from decimal import Decimal
from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field
from app.api.dependencies import get_context,get_session
from app.engines.logistics import LogisticsProductionService
router=APIRouter(prefix="/logistics",tags=["logistics"])
class Shipment(BaseModel):order_id:int;reference:str;origin_warehouse_id:str;destination:str;carrier:str;currency:str;cod_amount:Decimal=Field(default=0,ge=0);tracking_number:str|None=None
class Transition(BaseModel):status:str;event_id:str;location:str|None=None;note:str|None=None
@router.post("/shipments",status_code=201)
def create(body:Shipment,ctx=Depends(get_context),db=Depends(get_session)):
    x=LogisticsProductionService(db).create_shipment(ctx.tenant_id,**body.model_dump());return {"id":x.id,"reference":x.reference,"status":x.status,"tracking_number":x.tracking_number}
@router.post("/shipments/{shipment_id}/transition")
def transition(shipment_id:int,body:Transition,ctx=Depends(get_context),db=Depends(get_session)):
    x=LogisticsProductionService(db).transition(ctx.tenant_id,shipment_id,body.status,event_id=body.event_id,location=body.location,note=body.note);return {"id":x.id,"status":x.status}
