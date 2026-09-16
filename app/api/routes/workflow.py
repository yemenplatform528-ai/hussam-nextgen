from fastapi import APIRouter,Depends
from pydantic import BaseModel
from app.api.dependencies import get_context,get_session
from app.engines.workflow import WorkflowEngine
router=APIRouter(prefix="/workflows",tags=["workflows"])
class Definition(BaseModel):code:str;version:int;name:str;steps:dict;active:bool=True
class Start(BaseModel):definition_code:str;version:int;reference:str;aggregate_type:str;aggregate_id:str;context:dict|None=None
class Event(BaseModel):event_id:str;event_type:str;payload:dict|None=None
@router.post("/definitions",status_code=201)
def definition(body:Definition,ctx=Depends(get_context),db=Depends(get_session)):
    x=WorkflowEngine(db).register_definition(ctx.tenant_id,**body.model_dump());return {"id":x.id,"code":x.code,"version":x.version}
@router.post("/instances",status_code=201)
def start(body:Start,ctx=Depends(get_context),db=Depends(get_session)):
    x=WorkflowEngine(db).start(ctx.tenant_id,**body.model_dump());return {"id":x.id,"reference":x.reference,"status":x.status,"step":x.current_step}
@router.post("/instances/{instance_id}/events")
def event(instance_id:int,body:Event,ctx=Depends(get_context),db=Depends(get_session)):
    x=WorkflowEngine(db).apply_event(ctx.tenant_id,instance_id,**body.model_dump());return {"id":x.id,"status":x.status,"step":x.current_step}
