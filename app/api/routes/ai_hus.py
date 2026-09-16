from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.api.dependencies import get_context,get_session
from app.core.models.ai_hus import AIToolDefinition,AIRun,AIAction,HUSCompilation
from app.ai.runtime import create_run,propose_action,approve_action,complete_read_action,execute_read_action,AIError
from app.ai.intelligence import business_snapshot, generate_insights, save_memory, list_memories, plan_agent, record_evaluation
from decimal import Decimal
from app.hus.compiler import compile_spec,HUSCompileError
from app.hus.operational import compile_and_store, activate
from uuid import uuid4

router=APIRouter(tags=['ai-hus'])
class RunIn(BaseModel): purpose:str=Field(min_length=1,max_length=200); payload:dict={}; model:str|None=None
class ActionIn(BaseModel): run_id:str; tool_code:str; arguments:dict={}
class ApprovalIn(BaseModel): action_id:str
class ToolIn(BaseModel): code:str; name:str; description:str; risk:str='read'; input_schema:dict={}
class CompileIn(BaseModel): spec:dict

@router.get('/ai/tools')
def tools(ctx=Depends(get_context),db=Depends(get_session)):
    rows=db.scalars(select(AIToolDefinition).where(AIToolDefinition.tenant_id==ctx.tenant_id).order_by(AIToolDefinition.code)).all()
    return {'items':[{'code':x.code,'name':x.name,'risk':x.risk,'enabled':x.enabled,'input_schema':x.input_schema} for x in rows]}

@router.post('/ai/tools',status_code=201)
def register_tool(body:ToolIn,ctx=Depends(get_context),db=Depends(get_session)):
    if body.risk not in {'read','mutation','admin'}: raise AIError('invalid tool risk')
    x=AIToolDefinition(tenant_id=ctx.tenant_id,code=body.code,name=body.name,description=body.description,risk=body.risk,input_schema=body.input_schema,enabled=True)
    db.add(x); db.commit(); db.refresh(x); return {'code':x.code,'risk':x.risk,'enabled':x.enabled}

@router.post('/ai/runs',status_code=201)
def run(body:RunIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=create_run(db,ctx.tenant_id,ctx.user_id,body.purpose,body.payload,body.model)
    return {'id':x.id,'status':x.status,'input_hash':x.input_hash}

@router.post('/ai/actions',status_code=201)
def action(body:ActionIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=propose_action(db,ctx.tenant_id,ctx.user_id,body.run_id,body.tool_code,body.arguments)
    return {'id':x.id,'status':x.status,'risk':x.risk,'tool_code':x.tool_code}

@router.post('/ai/actions/{action_id}/approve')
def approve(action_id:str,ctx=Depends(get_context),db=Depends(get_session)):
    x=approve_action(db,ctx.tenant_id,ctx.user_id,action_id); return {'id':x.id,'status':x.status,'approved_by':x.approved_by}

@router.post('/ai/actions/{action_id}/execute')
def execute(action_id:str,ctx=Depends(get_context),db=Depends(get_session)):
    x=execute_read_action(db,ctx.tenant_id,ctx.user_id,action_id)
    return {'id':x.id,'status':x.status,'tool_code':x.tool_code,'result':x.result}

@router.get('/ai/runs/{run_id}')
def get_run(run_id:str,ctx=Depends(get_context),db=Depends(get_session)):
    x=db.scalar(select(AIRun).where(AIRun.id==run_id,AIRun.tenant_id==ctx.tenant_id));
    if not x: raise AIError('AI run not found in tenant')
    acts=db.scalars(select(AIAction).where(AIAction.run_id==run_id,AIAction.tenant_id==ctx.tenant_id)).all()
    return {'id':x.id,'status':x.status,'purpose':x.purpose,'model':x.model,'output':x.output,'actions':[{'id':a.id,'tool_code':a.tool_code,'risk':a.risk,'status':a.status,'approved_by':a.approved_by} for a in acts]}

@router.post('/hus/compile')
def compile_hus(body:CompileIn,ctx=Depends(get_context),db=Depends(get_session)):
    try:
        x, result = compile_and_store(db,ctx.tenant_id,ctx.user_id,body.spec)
    except HUSCompileError as e:
        return {'status':'rejected','diagnostics':[d.__dict__ for d in e.diagnostics]}
    return {'id':x.id,'status':x.status,'stages':result['stages'],'source_hash':x.source_hash,'contract_hash':x.contract_hash,'contract':x.contract}

@router.post('/hus/compilations/{compilation_id}/activate')
def activate_hus(compilation_id:str,ctx=Depends(get_context),db=Depends(get_session)):
    x=activate(db,ctx.tenant_id,ctx.user_id,compilation_id)
    return {'id':x.id,'status':x.status,'source_hash':x.source_hash,'contract_hash':x.contract_hash}

@router.get('/hus/active')
def active_hus(ctx=Depends(get_context),db=Depends(get_session)):
    x=db.scalar(select(HUSCompilation).where(HUSCompilation.tenant_id==ctx.tenant_id,HUSCompilation.status=='active').order_by(HUSCompilation.created_at.desc()))
    if not x: return {'active':None}
    return {'active':{'id':x.id,'status':x.status,'spec_version':x.spec_version,'source_hash':x.source_hash,'contract_hash':x.contract_hash,'contract':x.contract}}

@router.get('/hus/compilations/{compilation_id}')
def get_compilation(compilation_id:str,ctx=Depends(get_context),db=Depends(get_session)):
    x=db.scalar(select(HUSCompilation).where(HUSCompilation.id==compilation_id,HUSCompilation.tenant_id==ctx.tenant_id))
    if not x: raise AIError('HUS compilation not found in tenant')
    return {'id':x.id,'status':x.status,'spec_version':x.spec_version,'source_hash':x.source_hash,'contract':x.contract,'diagnostics':x.diagnostics}


class GoalIn(BaseModel): goal:str=Field(min_length=1,max_length=500)
class MemoryIn(BaseModel): key:str=Field(min_length=1,max_length=160); value:dict={}; source:str='user'
class EvaluationIn(BaseModel): run_id:str; metric:str=Field(min_length=1,max_length=100); score:Decimal; details:dict={}

@router.get('/ai/business-snapshot')
def ai_snapshot(ctx=Depends(get_context),db=Depends(get_session)):
    return business_snapshot(db,ctx.tenant_id)

@router.post('/ai/insights',status_code=201)
def ai_insights(ctx=Depends(get_context),db=Depends(get_session)):
    rows=generate_insights(db,ctx.tenant_id,ctx.user_id)
    return {'items':[{'id':x.id,'kind':x.kind,'severity':x.severity,'title':x.title,'evidence':x.evidence,'status':x.status} for x in rows]}

@router.get('/ai/memories')
def ai_memories(ctx=Depends(get_context),db=Depends(get_session)):
    rows=list_memories(db,ctx.tenant_id)
    return {'items':[{'id':x.id,'key':x.key,'value':x.value,'source':x.source,'updated_at':x.updated_at.isoformat()} for x in rows]}

@router.post('/ai/memories',status_code=201)
def ai_memory(body:MemoryIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=save_memory(db,ctx.tenant_id,ctx.user_id,body.key,body.value,body.source)
    return {'id':x.id,'key':x.key,'value':x.value,'source':x.source}

@router.post('/ai/agent/plan')
def ai_agent_plan(body:GoalIn,ctx=Depends(get_context),db=Depends(get_session)):
    return plan_agent(db,ctx.tenant_id,ctx.user_id,body.goal)

@router.post('/ai/evaluations',status_code=201)
def ai_evaluation(body:EvaluationIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=record_evaluation(db,ctx.tenant_id,ctx.user_id,body.run_id,body.metric,body.score,body.details)
    return {'id':x.id,'run_id':x.run_id,'metric':x.metric,'score':str(x.score)}
