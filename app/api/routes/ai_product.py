"""AI-04 product-lock and Control Center evidence endpoints."""
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.dependencies import get_context, get_session
from app.ai.product import record_provider_health, register_evaluation_suite, record_evaluation_result, build_release_gate, control_change, security_release_snapshot

router=APIRouter(tags=['ai-product'])


def developer_guard(ctx):
    if ctx.role not in {'owner','admin'}:
        raise HTTPException(status_code=403, detail='AI product control plane requires owner or admin role')

class HealthIn(BaseModel):
    provider_code: str
    status: str
    latency_ms: int|None=None
    error_class: str|None=None
    evidence: dict={}
class SuiteIn(BaseModel):
    code: str
    version: str
    checks: list[str]=Field(min_length=1)
    threshold: Decimal=Decimal('0.90')
class ResultIn(BaseModel):
    suite_code: str
    run_id: str
    metric: str
    score: Decimal
    evidence: dict={}
class GateIn(BaseModel):
    release_code: str
    required_checks: list[str]=Field(min_length=1)
    evidence: dict={}
class ControlIn(BaseModel):
    resource_type: str
    resource_code: str
    action: str
    before_state: dict={}
    after_state: dict={}

@router.post('/ai/product/provider-health',status_code=201)
def provider_health(body:HealthIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=record_provider_health(db,ctx.tenant_id,**body.model_dump())
    return {'id':x.id,'provider_code':x.provider_code,'status':x.status}

@router.post('/ai/product/evaluation-suites',status_code=201)
def suite(body:SuiteIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=register_evaluation_suite(db,ctx.tenant_id,**body.model_dump())
    return {'id':x.id,'code':x.code,'version':x.version,'threshold':str(x.threshold)}

@router.post('/ai/product/evaluation-results',status_code=201)
def result(body:ResultIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=record_evaluation_result(db,ctx.tenant_id,**body.model_dump())
    return {'id':x.id,'metric':x.metric,'score':str(x.score),'passed':x.passed}

@router.post('/ai/product/release-gate',status_code=200)
def release_gate(body:GateIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=build_release_gate(db,ctx.tenant_id,**body.model_dump())
    return {'id':x.id,'release_code':x.release_code,'status':x.status,'passed_checks':x.passed_checks,'blocked_reason':x.blocked_reason}

@router.post('/ai/product/control-change',status_code=201)
def change(body:ControlIn,ctx=Depends(get_context),db=Depends(get_session)):
    developer_guard(ctx)
    x=control_change(db,ctx.tenant_id,ctx.actor_id,**body.model_dump())
    return {'id':x.id,'resource_type':x.resource_type,'resource_code':x.resource_code,'status':x.status}

@router.get('/ai/product/security-snapshot')
def snapshot(ctx=Depends(get_context),db=Depends(get_session)):
    return security_release_snapshot(db,ctx.tenant_id)
