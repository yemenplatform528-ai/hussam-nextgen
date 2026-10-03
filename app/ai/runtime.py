"""Provider-neutral AI control plane. Model providers are adapters; the Core remains authoritative."""
from hashlib import sha256
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.ai_hus import AIToolDefinition, AIRun, AIAction, HUSCompilation
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

def approve_action(db:Session,tenant_id:int,actor_id:str,action_id:str, *, compilation_id:str|None=None, step_id:str|None=None, idempotency_key:str|None=None, auth_source:str|None=None, oidc_subject:str|None=None, oidc_issuer:str|None=None):
    action=db.scalar(select(AIAction).where(AIAction.id==action_id,AIAction.tenant_id==tenant_id).with_for_update())
    if not action: raise AIError('AI action not found in tenant')
    if action.status!='pending_approval': raise AIError('AI action is not awaiting approval')
    if action.risk == MUTATION:
        if not compilation_id or not step_id or not idempotency_key:
            raise AIError('mutation approval requires compilation, step, and idempotency binding')
        compilation=db.scalar(select(HUSCompilation).where(HUSCompilation.id==compilation_id,HUSCompilation.tenant_id==tenant_id,HUSCompilation.status=='active'))
        if not compilation: raise AIError('active HUS compilation not found in tenant')
        plan=(compilation.contract or {}).get('execution_plan') or (compilation.contract or {}).get('ir')
        steps={s.get('id'):s for w in (plan or {}).get('workflows',[]) for s in w.get('steps',[]) if isinstance(s,dict) and s.get('id')}
        step=steps.get(step_id)
        if not step: raise AIError('HUS execution step is not present in the active plan')
        a=step.get('action') or {}
        bound_action=f"{a.get('engine')}.{a.get('capability')}"
        if bound_action != action.tool_code: raise AIError('approval binding action mismatch')
        plan_hash=compilation.contract_hash or sha256(canonical(compilation.contract or {}).encode()).hexdigest()
        arguments_hash=sha256(canonical(action.arguments).encode()).hexdigest()
        execution_binding={'compilation_id':compilation_id,'step_id':step_id,'plan_hash':plan_hash,'action':bound_action,'idempotency_key':idempotency_key,'arguments_hash':arguments_hash}
    else:
        execution_binding=None
    action.status='approved'; action.approved_by=actor_id
    provenance={'auth_source':auth_source,'oidc_subject':oidc_subject,'oidc_issuer':oidc_issuer}
    if execution_binding is not None: provenance['execution_binding']=execution_binding
    action.approval_provenance=provenance
    run=db.scalar(select(AIRun).where(AIRun.id==action.run_id,AIRun.tenant_id==tenant_id)); run.status='approved' if run else 'approved'
    _event(db,tenant_id,'ai.action.approved',action.id,{'approved_by':actor_id,'auth_source':auth_source,'oidc_subject':oidc_subject,'oidc_issuer':oidc_issuer,'execution_binding':execution_binding})
    from app.ai.foundation import trace
    trace(db,tenant_id,action.run_id,'AUTHORIZATION','HUMAN_APPROVAL_ACCEPTED',{'action_id':action.id,'approver_id':actor_id,'auth_source':auth_source,'oidc_subject':oidc_subject,'oidc_issuer':oidc_issuer,'execution_binding':execution_binding})
    db.commit(); return action

def complete_read_action(db:Session,tenant_id:int,action_id:str,result:dict):
    action=db.scalar(select(AIAction).where(AIAction.id==action_id,AIAction.tenant_id==tenant_id).with_for_update())
    if not action or action.risk!=READ or action.status!='approved': raise AIError('read action cannot be completed')
    action.result=result; action.status='completed'; run=db.scalar(select(AIRun).where(AIRun.id==action.run_id,AIRun.tenant_id==tenant_id))
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
    """Fail closed: AI mutations must use the governed HUS execution boundary."""
    raise AIError('AI mutation execution requires the governed HUS runtime and authoritative approval verification')
