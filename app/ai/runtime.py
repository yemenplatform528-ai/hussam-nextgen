"""Provider-neutral AI control plane. Model providers are adapters; the Core remains authoritative."""
from hashlib import sha256
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.ai_hus import AIToolDefinition, AIRun, AIAction
from app.core.models.governance import OutboxEvent
from app.hus.compiler import canonical

class AIError(ValueError): pass
READ='read'; MUTATION='mutation'; ADMIN='admin'

def _event(db, tenant_id, typ, aggregate_id, payload):
    db.add(OutboxEvent(event_id=str(uuid4()),tenant_id=tenant_id,event_type=typ,aggregate_type='ai',aggregate_id=str(aggregate_id),payload=payload,published=False))

def create_run(db: Session, tenant_id: int, actor_id: str, purpose: str, payload: dict, model: str|None=None):
    run=AIRun(id=str(uuid4()),tenant_id=tenant_id,actor_id=actor_id,purpose=purpose,status='proposed',model=model,input_hash=sha256(canonical(payload).encode()).hexdigest())
    db.add(run); _event(db,tenant_id,'ai.run.proposed',run.id,{'purpose':purpose,'model':model}); db.commit(); return run

def propose_action(db: Session, tenant_id:int, actor_id:str, run_id:str, tool_code:str, arguments:dict):
    run=db.scalar(select(AIRun).where(AIRun.id==run_id,AIRun.tenant_id==tenant_id))
    tool=db.scalar(select(AIToolDefinition).where(AIToolDefinition.tenant_id==tenant_id,AIToolDefinition.code==tool_code,AIToolDefinition.enabled.is_(True)))
    if not run: raise AIError('AI run not found in tenant')
    if not tool: raise AIError('AI tool not found or disabled')
    if run.actor_id != actor_id: raise AIError('AI run actor mismatch')
    if tool.risk not in {READ,MUTATION,ADMIN}: raise AIError('invalid tool risk')
    action=AIAction(id=str(uuid4()),tenant_id=tenant_id,run_id=run_id,tool_code=tool_code,risk=tool.risk,arguments=arguments,status='approved' if tool.risk==READ else 'pending_approval')
    db.add(action); run.status='waiting_approval' if tool.risk != READ else 'running'; _event(db,tenant_id,'ai.action.proposed',action.id,{'run_id':run_id,'tool':tool_code,'risk':tool.risk}); db.commit(); return action

def approve_action(db:Session,tenant_id:int,actor_id:str,action_id:str):
    action=db.scalar(select(AIAction).where(AIAction.id==action_id,AIAction.tenant_id==tenant_id).with_for_update())
    if not action: raise AIError('AI action not found in tenant')
    if action.status!='pending_approval': raise AIError('AI action is not awaiting approval')
    action.status='approved'; action.approved_by=actor_id
    run=db.scalar(select(AIRun).where(AIRun.id==action.run_id,AIRun.tenant_id==tenant_id)); run.status='approved' if run else 'approved'
    _event(db,tenant_id,'ai.action.approved',action.id,{'approved_by':actor_id}); db.commit(); return action

def complete_read_action(db:Session,tenant_id:int,action_id:str,result:dict):
    action=db.scalar(select(AIAction).where(AIAction.id==action_id,AIAction.tenant_id==tenant_id).with_for_update())
    if not action or action.risk!=READ or action.status!='approved': raise AIError('read action cannot be completed')
    action.result=result; action.status='completed'; run=db.scalar(select(AIRun).where(AIRun.id==action.run_id,AIRun.tenant_id==tenant_id));
    if run: run.status='completed'; run.output=result
    _event(db,tenant_id,'ai.action.completed',action.id,{'tool':action.tool_code}); db.commit(); return action

def execute_read_action(db:Session,tenant_id:int,actor_id:str,action_id:str):
    """Execute only an approved READ action through the explicit tool registry."""
    from app.ai.tools import execute_read_tool
    action=db.scalar(select(AIAction).where(AIAction.id==action_id,AIAction.tenant_id==tenant_id).with_for_update())
    if not action: raise AIError('AI action not found in tenant')
    if action.risk != READ or action.status != 'approved': raise AIError('only approved read actions can execute')
    run=db.scalar(select(AIRun).where(AIRun.id==action.run_id,AIRun.tenant_id==tenant_id))
    if not run or run.actor_id != actor_id: raise AIError('AI run actor mismatch')
    result=execute_read_tool(db,tenant_id,action.tool_code,action.arguments)
    action.result=result; action.status='completed'; run.status='completed'; run.output=result
    _event(db,tenant_id,'ai.action.completed',action.id,{'tool':action.tool_code})
    db.commit(); return action

def execute_approved_mutation(db:Session,tenant_id:int,actor_id:str,action_id:str,approval_ref:str|None=None):
    from app.ai.tools import execute_mutation_tool
    action=db.scalar(select(AIAction).where(AIAction.id==action_id,AIAction.tenant_id==tenant_id).with_for_update())
    if not action: raise AIError('AI action not found in tenant')
    if action.risk not in {MUTATION,ADMIN} or action.status!='approved': raise AIError('only approved mutation actions can execute')
    run=db.scalar(select(AIRun).where(AIRun.id==action.run_id,AIRun.tenant_id==tenant_id))
    if not run or run.actor_id!=actor_id: raise AIError('AI run actor mismatch')
    result=execute_mutation_tool(db,tenant_id,action.tool_code,action.arguments)
    action.result=result; action.status='completed'; run.status='completed'; run.output=result
    _event(db,tenant_id,'ai.action.executed',action.id,{'tool':action.tool_code,'approval_ref':approval_ref})
    db.commit(); return action
