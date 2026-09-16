from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.models.workflow import WorkflowDefinition, WorkflowInstance, WorkflowTransition, WorkflowTask
from app.core.models.governance import OutboxEvent

class WorkflowError(ValueError): pass

@dataclass(frozen=True)
class TransitionRule:
    event_type: str
    to_step: str

class WorkflowEngine:
    """Deterministic orchestration state machine. It records facts and emits commands/events; domain engines remain authoritative."""
    def __init__(self, db: Session): self.db = db

    def _emit(self, tenant_id, event_type, instance_id, payload):
        from uuid import uuid4
        self.db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type,
            aggregate_type='workflow_instance', aggregate_id=str(instance_id), payload=payload, published=False))

    def register_definition(self, tenant_id: int, *, code: str, version: int, name: str, steps: dict, active: bool=True):
        if tenant_id <= 0 or not code or version <= 0 or not name or not steps: raise WorkflowError('valid workflow definition is required')
        if 'start' not in steps or not isinstance(steps, dict): raise WorkflowError('definition must contain start step')
        if self.db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.tenant_id==tenant_id, WorkflowDefinition.code==code, WorkflowDefinition.version==version)):
            raise WorkflowError('workflow definition version already exists')
        d=WorkflowDefinition(tenant_id=tenant_id,code=code,version=version,name=name,definition_json=steps,active=active)
        self.db.add(d); self.db.flush(); self.db.commit(); self.db.refresh(d); return d

    def start(self, tenant_id:int, *, definition_code:str, version:int, reference:str, aggregate_type:str, aggregate_id:str, context:dict|None=None):
        d=self.db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.tenant_id==tenant_id,WorkflowDefinition.code==definition_code,WorkflowDefinition.version==version,WorkflowDefinition.active.is_(True)))
        if d is None: raise WorkflowError('active workflow definition not found in tenant')
        if self.db.scalar(select(WorkflowInstance).where(WorkflowInstance.tenant_id==tenant_id,WorkflowInstance.reference==reference)): raise WorkflowError('duplicate workflow reference')
        start=d.definition_json.get('start')
        if start not in d.definition_json: raise WorkflowError('start step is not defined')
        i=WorkflowInstance(tenant_id=tenant_id,definition_id=d.id,reference=reference,aggregate_type=aggregate_type,aggregate_id=str(aggregate_id),current_step=start,status='running',context_json=context or {})
        self.db.add(i); self.db.flush(); self._ensure_task(i, start); self._emit(tenant_id,'workflow.started',i.id,{'reference':reference,'step':start})
        try: self.db.commit(); self.db.refresh(i); return i
        except IntegrityError: self.db.rollback(); raise WorkflowError('duplicate workflow reference')

    def _instance(self, tenant_id, instance_id, lock=False):
        q=select(WorkflowInstance).where(WorkflowInstance.id==instance_id,WorkflowInstance.tenant_id==tenant_id)
        if lock: q=q.with_for_update()
        i=self.db.scalar(q)
        if i is None: raise WorkflowError('workflow instance not found in tenant')
        return i

    def _definition(self, tenant_id, instance):
        d=self.db.scalar(select(WorkflowDefinition).where(WorkflowDefinition.id==instance.definition_id,WorkflowDefinition.tenant_id==tenant_id))
        if d is None: raise WorkflowError('workflow definition not found in tenant')
        return d

    def _ensure_task(self, instance, step):
        spec=instance and self._definition(instance.tenant_id,instance).definition_json.get(step,{})
        task_key=str(spec.get('task_key',step)) if isinstance(spec,dict) else step
        existing=self.db.scalar(select(WorkflowTask).where(WorkflowTask.tenant_id==instance.tenant_id,WorkflowTask.instance_id==instance.id,WorkflowTask.task_key==task_key))
        if existing is None:
            self.db.add(WorkflowTask(tenant_id=instance.tenant_id,instance_id=instance.id,step=step,task_key=task_key,status='pending'))

    def apply_event(self, tenant_id:int, instance_id:int, *, event_id:str, event_type:str, payload:dict|None=None):
        if not event_id or not event_type: raise WorkflowError('event id and type are required')
        existing=self.db.scalar(select(WorkflowTransition).where(WorkflowTransition.tenant_id==tenant_id,WorkflowTransition.event_id==event_id))
        if existing: return self._instance(tenant_id,instance_id)
        i=self._instance(tenant_id,instance_id,lock=True)
        if i.status not in ('running','waiting'): raise WorkflowError('workflow is not active')
        d=self._definition(tenant_id,i); spec=d.definition_json.get(i.current_step)
        if not isinstance(spec,dict): raise WorkflowError('current workflow step is invalid')
        transitions=spec.get('on',{})
        target=transitions.get(event_type)
        if target is None: raise WorkflowError('event is not accepted by current step')
        if target not in d.definition_json: raise WorkflowError('target step is not defined')
        from_step = i.current_step
        self.db.add(WorkflowTransition(tenant_id=tenant_id,instance_id=i.id,event_id=event_id,from_step=from_step,to_step=target,event_type=event_type,payload_json=payload or {},occurred_at=datetime.now(timezone.utc)))
        i.current_step=target; i.status='completed' if bool(d.definition_json.get(target,{}).get('terminal',False)) else 'running'; i.updated_at=datetime.now(timezone.utc)
        self._ensure_task(i,target); self._emit(tenant_id,'workflow.transitioned',i.id,{'reference':i.reference,'event_type':event_type,'from_step':from_step,'to_step':target,'event_id':event_id})
        try: self.db.commit(); return i
        except IntegrityError:
            self.db.rollback(); existing=self.db.scalar(select(WorkflowTransition).where(WorkflowTransition.tenant_id==tenant_id,WorkflowTransition.event_id==event_id))
            if existing: return self._instance(tenant_id,instance_id)
            raise WorkflowError('workflow transition conflict')

    def cancel(self, tenant_id:int, instance_id:int, *, event_id:str):
        i=self._instance(tenant_id,instance_id,lock=True)
        if i.status in ('completed','cancelled'): raise WorkflowError('workflow is already terminal')
        i.status='cancelled'; i.updated_at=datetime.now(timezone.utc)
        self._emit(tenant_id,'workflow.cancelled',i.id,{'reference':i.reference,'event_id':event_id})
        self.db.commit(); return i
