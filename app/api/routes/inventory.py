from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.dependencies import get_context, get_session
from app.core.contracts import StockMovement
from app.engines.inventory.production import InventoryProductionService

router=APIRouter(prefix="/inventory", tags=["inventory"])
class ItemIn(BaseModel): id:str; name:str; unit_code:str="unit"
class WarehouseIn(BaseModel): id:str; name:str; allow_negative_stock:bool=False
class MovementIn(BaseModel): item_id:str; warehouse_id:str; quantity:Decimal=Field(gt=0); direction:str; reference:str; destination_warehouse_id:str|None=None
@router.post("/items", status_code=201)
def create_item(body:ItemIn, ctx=Depends(get_context), db=Depends(get_session)):
    x=InventoryProductionService(db).create_item(ctx.tenant_id, body.id, body.name, body.unit_code)
    return {"id":x.id,"name":x.name,"unit_code":x.unit_code}
@router.post("/warehouses", status_code=201)
def create_warehouse(body:WarehouseIn, ctx=Depends(get_context), db=Depends(get_session)):
    x=InventoryProductionService(db).create_warehouse(ctx.tenant_id, body.id, body.name, body.allow_negative_stock)
    return {"id":x.id,"name":x.name,"allow_negative_stock":x.allow_negative_stock}
@router.post("/movements", status_code=201)
def movement(body:MovementIn, ctx=Depends(get_context), db=Depends(get_session)):
    x=InventoryProductionService(db).record(ctx.tenant_id, StockMovement(item_id=body.item_id,warehouse_id=body.warehouse_id,quantity=body.quantity,direction=body.direction,reference=body.reference,destination_warehouse_id=body.destination_warehouse_id), actor_id=ctx.user_id)
    return {"id":x.id,"reference":x.reference,"direction":x.direction,"quantity":str(x.quantity)}
@router.get("/stock/{item_id}/{warehouse_id}")
def stock(item_id:str, warehouse_id:str, ctx=Depends(get_context), db=Depends(get_session)):
    x=InventoryProductionService(db).snapshot(ctx.tenant_id,item_id,warehouse_id)
    return {"item_id":x.item_id,"warehouse_id":x.warehouse_id,"on_hand":str(x.on_hand),"reserved":str(x.reserved),"available":str(x.available)}
