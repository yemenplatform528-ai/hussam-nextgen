"""Persistence and activation lifecycle for compiled HUS contracts."""
from hashlib import sha256
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.ai_hus import HUSCompilation
from app.hus.compiler import compile_spec, HUSCompileError, canonical

def compile_and_store(db: Session, tenant_id: int, actor_id: str, spec: dict):
    result=compile_spec(spec)
    x=HUSCompilation(id=str(uuid4()),tenant_id=tenant_id,actor_id=actor_id,spec_version=spec['spec_version'],source_hash=result['source_hash'],contract_hash=result['contract_hash'],status='compiled',contract=result['contract'],diagnostics=[])
    db.add(x); db.commit(); db.refresh(x)
    return x, result

def activate(db: Session, tenant_id: int, actor_id: str, compilation_id: str):
    x=db.scalar(select(HUSCompilation).where(HUSCompilation.id==compilation_id,HUSCompilation.tenant_id==tenant_id).with_for_update())
    if not x: raise ValueError('HUS compilation not found in tenant')
    if x.status not in {'compiled','active'}: raise ValueError('only a compiled HUS contract can be activated')
    active=db.scalars(select(HUSCompilation).where(HUSCompilation.tenant_id==tenant_id,HUSCompilation.status=='active',HUSCompilation.id!=compilation_id).with_for_update()).all()
    for old in active: old.status='superseded'
    x.status='active'
    db.commit(); db.refresh(x)
    return x

from app.core.models.amazon_completion import HUSExecutionRecord

def execute_compiled_action(db: Session, tenant_id: int, actor_id: str, compilation_id: str, action: str, arguments: dict, approved: bool = False, approval_ref: str|None = None, idempotency_key: str|None = None):
    """Compatibility facade over HUS-03 SovereignRuntime.

    Legacy callers may pass an action name; HUS-03 itself executes only an identified
    compiled-plan step, so this facade resolves a unique matching step and then delegates.
    """
    from .runtime import SovereignRuntime, HUSRuntimeError
    x=db.scalar(select(HUSCompilation).where(HUSCompilation.id==compilation_id,HUSCompilation.tenant_id==tenant_id))
    if not x or x.status != 'active':
        raise HUSRuntimeError('active HUS compilation not found')
    matches=[]
    for workflow in ((x.contract or {}).get('execution_plan') or (x.contract or {}).get('ir') or {}).get('workflows',[]):
        for step in workflow.get('steps',[]):
            a=step.get('action',{})
            if f"{a.get('engine')}.{a.get('capability')}" == action:
                matches.append(step.get('id'))
    if len(matches) != 1:
        raise HUSRuntimeError('action must resolve to exactly one compiled execution step')
    runtime=SovereignRuntime(db)
    if action == 'marketplace.marketplace.read':
        def handler(db, ctx, args):
            from app.ai.tools import execute_read_tool
            return execute_read_tool(db,ctx.tenant_id,args.get('tool_code','marketplace.overview'),args.get('arguments',{}))
        runtime.register_read_handler(action, handler)
    return runtime.execute_step(tenant_id, actor_id, compilation_id, matches[0], arguments, approval_ref=approval_ref, approved=approved, idempotency_key=idempotency_key)
