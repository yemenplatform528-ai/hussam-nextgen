from uuid import uuid4
from hashlib import sha256
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.api.dependencies import get_context, get_session
from app.core.models.developer_platform import DeveloperExtension, DeveloperExtensionVersion, DeveloperExtensionAudit

router=APIRouter(prefix='/developer',tags=['developer-platform'])

def developer_guard(ctx):
    if ctx.role not in {'owner','admin'}:
        raise HTTPException(status_code=403, detail='developer platform requires owner or admin role')

class ExtensionIn(BaseModel):
    code:str=Field(min_length=2,max_length=120)
    name:str=Field(min_length=1,max_length=200)
    description:str=''
    extension_type:str='module'
    market_scope:list[str]=Field(default_factory=list)
    capabilities:list[str]=Field(default_factory=list)
    permissions:list[str]=Field(default_factory=list)

class VersionIn(BaseModel):
    version:str=Field(min_length=1,max_length=40)
    manifest:dict=Field(default_factory=dict)
    source_hash:str=Field(min_length=64,max_length=64)
    compatibility:dict=Field(default_factory=dict)
    test_status:str='pending'
    rollback_version:str|None=None

@router.get('/extensions')
def list_extensions(ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    rows=db.scalars(select(DeveloperExtension).where(DeveloperExtension.tenant_id==ctx.tenant_id).order_by(DeveloperExtension.code)).all()
    return {'items':[{'id':x.id,'code':x.code,'name':x.name,'type':x.extension_type,'status':x.status,'market_scope':x.market_scope,'capabilities':x.capabilities} for x in rows]}

@router.post('/extensions',status_code=201)
def create_extension(body:ExtensionIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    if body.extension_type not in {'config','module','adapter','platform'}: raise HTTPException(status_code=400,detail='invalid extension_type')
    if db.scalar(select(DeveloperExtension).where(DeveloperExtension.tenant_id==ctx.tenant_id,DeveloperExtension.code==body.code)): raise HTTPException(status_code=409,detail='extension code already exists')
    x=DeveloperExtension(id=uuid4().hex,tenant_id=ctx.tenant_id,code=body.code,name=body.name,description=body.description,extension_type=body.extension_type,market_scope=body.market_scope,capabilities=body.capabilities,permissions=body.permissions,created_by=ctx.user_id)
    db.add(x); db.flush(); db.add(DeveloperExtensionAudit(extension_id=x.id,actor_id=ctx.user_id,action='created',details={'code':x.code})); db.commit(); db.refresh(x)
    return {'id':x.id,'code':x.code,'status':x.status}

@router.post('/extensions/{extension_id}/versions',status_code=201)
def create_version(extension_id:str,body:VersionIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=db.scalar(select(DeveloperExtension).where(DeveloperExtension.id==extension_id,DeveloperExtension.tenant_id==ctx.tenant_id))
    if not x: raise HTTPException(status_code=404,detail='extension not found')
    if body.test_status not in {'pending','passed','failed'}: raise HTTPException(status_code=400,detail='invalid test_status')
    if not all(c in x.capabilities for c in body.manifest.get('capabilities', x.capabilities)): raise HTTPException(status_code=400,detail='manifest capability exceeds extension declaration')
    v=DeveloperExtensionVersion(id=uuid4().hex,extension_id=x.id,version=body.version,manifest=body.manifest,source_hash=body.source_hash,compatibility=body.compatibility,test_status=body.test_status,rollback_version=body.rollback_version,created_by=ctx.user_id)
    db.add(v); db.add(DeveloperExtensionAudit(extension_id=x.id,actor_id=ctx.user_id,action='version_created',version=body.version,details={'source_hash':body.source_hash,'test_status':body.test_status})); x.status='testing'; db.commit()
    return {'id':v.id,'extension_id':x.id,'version':v.version,'status':v.release_status,'source_hash':v.source_hash}

@router.post('/extensions/{extension_id}/versions/{version}/publish')
def publish_version(extension_id:str,version:str,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=db.scalar(select(DeveloperExtension).where(DeveloperExtension.id==extension_id,DeveloperExtension.tenant_id==ctx.tenant_id))
    if not x: raise HTTPException(status_code=404,detail='extension not found')
    v=db.scalar(select(DeveloperExtensionVersion).where(DeveloperExtensionVersion.extension_id==x.id,DeveloperExtensionVersion.version==version))
    if not v: raise HTTPException(status_code=404,detail='extension version not found')
    if v.test_status!='passed': raise HTTPException(status_code=409,detail='version must pass tests before publish')
    v.release_status='published'; x.status='published'; db.add(DeveloperExtensionAudit(extension_id=x.id,actor_id=ctx.user_id,action='published',version=version)); db.commit()
    return {'id':x.id,'version':version,'status':v.release_status}

@router.post('/extensions/{extension_id}/versions/{version}/activate')
def activate_version(extension_id:str,version:str,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=db.scalar(select(DeveloperExtension).where(DeveloperExtension.id==extension_id,DeveloperExtension.tenant_id==ctx.tenant_id))
    if not x: raise HTTPException(status_code=404,detail='extension not found')
    v=db.scalar(select(DeveloperExtensionVersion).where(DeveloperExtensionVersion.extension_id==x.id,DeveloperExtensionVersion.version==version))
    if not v: raise HTTPException(status_code=404,detail='extension version not found')
    if v.release_status!='published': raise HTTPException(status_code=409,detail='version must be published before activation')
    v.release_status='active'; x.status='active'; db.add(DeveloperExtensionAudit(extension_id=x.id,actor_id=ctx.user_id,action='activated',version=version)); db.commit()
    return {'id':x.id,'version':version,'status':v.release_status}

@router.get('/extensions/{extension_id}/manifest')
def extension_manifest(extension_id:str,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=db.scalar(select(DeveloperExtension).where(DeveloperExtension.id==extension_id,DeveloperExtension.tenant_id==ctx.tenant_id))
    if not x: raise HTTPException(status_code=404,detail='extension not found')
    versions=db.scalars(select(DeveloperExtensionVersion).where(DeveloperExtensionVersion.extension_id==x.id).order_by(DeveloperExtensionVersion.created_at.desc())).all()
    return {'extension':{'id':x.id,'code':x.code,'name':x.name,'type':x.extension_type,'status':x.status,'market_scope':x.market_scope,'capabilities':x.capabilities,'permissions':x.permissions},'versions':[{'version':v.version,'status':v.release_status,'test_status':v.test_status,'source_hash':v.source_hash,'compatibility':v.compatibility,'manifest':v.manifest} for v in versions]}