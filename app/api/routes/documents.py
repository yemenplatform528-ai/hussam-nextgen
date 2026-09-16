from fastapi import APIRouter,Depends
from pydantic import BaseModel
from app.api.dependencies import get_context,get_session
from app.engines.documents import DocumentEngine
router=APIRouter(prefix="/documents",tags=["documents"])
class Create(BaseModel):document_type:str;reference:str;title:str;metadata:dict|None=None
class Link(BaseModel):aggregate_type:str;aggregate_id:str;relation:str="attachment"
@router.post("",status_code=201)
def create(body:Create,ctx=Depends(get_context),db=Depends(get_session)):
    x=DocumentEngine(db).create(ctx.tenant_id,document_type=body.document_type,reference=body.reference,title=body.title,metadata=body.metadata);return {"id":x.id,"reference":x.reference,"status":x.status}
@router.post("/{document_id}/finalize")
def finalize(document_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=DocumentEngine(db).finalize(ctx.tenant_id,document_id);return {"id":x.id,"status":x.status}
@router.post("/{document_id}/link")
def link(document_id:int,body:Link,ctx=Depends(get_context),db=Depends(get_session)):
    x=DocumentEngine(db).link(ctx.tenant_id,document_id,aggregate_type=body.aggregate_type,aggregate_id=body.aggregate_id,relation=body.relation);return {"id":x.id,"document_id":x.document_id}
