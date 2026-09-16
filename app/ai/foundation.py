"""AI-01 foundation services: registry, memory, routing, traces and usage."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.ai_foundation import AIProviderConfig, AIModelRoute, AIAgentDefinition, AIMemoryRecord, AITraceEvent, AIUsageEvent
from app.core.models.ai_hus import AIToolDefinition
from app.core.models.governance import OutboxEvent
from .contracts import AgentContract, DataClass, MemoryType, ModelRouteDecision, ModelRouteRequest, ToolContract


def _now(): return datetime.now(timezone.utc)

def _event(db, tenant_id, event_type, aggregate_id, payload):
    db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type, aggregate_type="ai_foundation", aggregate_id=str(aggregate_id), payload=payload, published=False))


def register_agent(db: Session, tenant_id: int, contract: AgentContract, system_policy: str) -> AIAgentDefinition:
    if not contract.scopes: raise ValueError("agent must declare at least one scope")
    x = db.scalar(select(AIAgentDefinition).where(AIAgentDefinition.tenant_id == tenant_id, AIAgentDefinition.code == contract.code))
    if x:
        x.name = contract.code; x.role = contract.role; x.system_policy = system_policy
        x.scopes = contract.scopes; x.tool_codes = contract.tool_codes; x.data_classes = [x.value for x in contract.data_classes]
        x.risk_class = contract.risk_class; x.approval_mode = contract.approval_mode; x.enabled = True
    else:
        x = AIAgentDefinition(id=str(uuid4()), tenant_id=tenant_id, code=contract.code, name=contract.code, role=contract.role,
            system_policy=system_policy, scopes=contract.scopes, tool_codes=contract.tool_codes,
            data_classes=[v.value for v in contract.data_classes], risk_class=contract.risk_class,
            approval_mode=contract.approval_mode, enabled=True)
        db.add(x)
    _event(db, tenant_id, "ai.agent.registered", x.id, {"code": contract.code, "role": contract.role})
    db.commit(); db.refresh(x); return x


def register_tool_contract(db: Session, tenant_id: int, contract: ToolContract, *, handler_key: str | None = None) -> AIToolDefinition:
    if contract.action_class.value in {"confirm", "execute"} and not contract.requires_approval:
        raise ValueError("mutating AI tools must require approval")
    x = db.scalar(select(AIToolDefinition).where(AIToolDefinition.tenant_id == tenant_id, AIToolDefinition.code == contract.code))
    risk = "admin" if contract.risk_class in {"high", "critical"} else ("mutation" if contract.action_class.value in {"confirm", "execute"} else "read")
    if x:
        x.name = contract.code; x.description = contract.description; x.risk = risk; x.input_schema = contract.input_schema; x.enabled = True
        x.side_effect_class = contract.action_class.value; x.data_classification = [v.value for v in contract.data_classes]
        x.approval_required = contract.requires_approval; x.idempotency_required = contract.idempotent; x.handler_key = handler_key
    else:
        x = AIToolDefinition(tenant_id=tenant_id, code=contract.code, name=contract.code, description=contract.description,
            risk=risk, input_schema=contract.input_schema, enabled=True)
        for name, value in {"side_effect_class": contract.action_class.value, "data_classification": [v.value for v in contract.data_classes],
                            "approval_required": contract.requires_approval, "idempotency_required": contract.idempotent, "handler_key": handler_key}.items():
            setattr(x, name, value)
        db.add(x)
    _event(db, tenant_id, "ai.tool.registered", x.id, {"code": contract.code, "action_class": contract.action_class.value})
    db.commit(); db.refresh(x); return x


def remember(db: Session, tenant_id: int, *, memory_type: MemoryType, key: str, value: dict, source: str,
             owner_id: str | None = None, agent_code: str | None = None, trust: str = "unverified", ttl_seconds: int | None = None):
    if memory_type == MemoryType.USER_PREFERENCE and not owner_id:
        raise ValueError("user_preference memory requires owner_id")
    expires = _now().replace(microsecond=0)
    if ttl_seconds is not None:
        from datetime import timedelta
        expires = expires + timedelta(seconds=ttl_seconds)
    else:
        expires = None
    x = AIMemoryRecord(id=str(uuid4()), tenant_id=tenant_id, owner_id=owner_id, agent_code=agent_code,
        memory_type=memory_type.value, key=key, value=value, source=source, trust=trust, expires_at=expires)
    db.add(x); _event(db, tenant_id, "ai.memory.recorded", x.id, {"memory_type": memory_type.value, "key": key, "source": source})
    db.commit(); db.refresh(x); return x


def revoke_memory(db: Session, tenant_id: int, memory_id: str):
    x = db.scalar(select(AIMemoryRecord).where(AIMemoryRecord.id == memory_id, AIMemoryRecord.tenant_id == tenant_id))
    if not x: raise ValueError("AI memory not found in tenant")
    if not x.revocable: raise ValueError("AI memory is not revocable")
    x.revoked_at = _now(); _event(db, tenant_id, "ai.memory.revoked", x.id, {})
    db.commit(); return x



def register_provider(db: Session, tenant_id: int, *, code: str, provider_kind: str, endpoint_ref: str | None = None, credential_ref: str | None = None, privacy_class: str = "standard", enabled: bool = False):
    if not code or not provider_kind: raise ValueError("provider code and kind are required")
    x = db.scalar(select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id, AIProviderConfig.code == code))
    if x:
        x.provider_kind = provider_kind; x.endpoint_ref = endpoint_ref; x.credential_ref = credential_ref
        x.privacy_class = privacy_class; x.enabled = enabled; x.updated_at = _now()
    else:
        x = AIProviderConfig(id=str(uuid4()), tenant_id=tenant_id, code=code, provider_kind=provider_kind, endpoint_ref=endpoint_ref,
            credential_ref=credential_ref, privacy_class=privacy_class, enabled=enabled, created_at=_now(), updated_at=_now())
        db.add(x)
    _event(db, tenant_id, "ai.provider.configured", x.id, {"code": code, "provider_kind": provider_kind, "enabled": enabled})
    db.commit(); db.refresh(x); return x


def register_model_route(db: Session, tenant_id: int, *, route_code: str, provider_code: str, model_code: str, task_class: str,
                         priority: int = 100, max_input_tokens: int | None = None, structured_output: bool = False,
                         tool_calling: bool = False, policy: dict | None = None):
    provider = db.scalar(select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id, AIProviderConfig.code == provider_code, AIProviderConfig.enabled.is_(True)))
    if not provider: raise ValueError("AI provider must be registered and enabled before a model route can be enabled")
    x = db.scalar(select(AIModelRoute).where(AIModelRoute.tenant_id == tenant_id, AIModelRoute.route_code == route_code))
    values = dict(provider_code=provider_code, model_code=model_code, task_class=task_class, priority=priority, max_input_tokens=max_input_tokens,
                  structured_output=structured_output, tool_calling=tool_calling, enabled=True, policy=policy or {})
    if x:
        for k, v in values.items(): setattr(x, k, v)
    else:
        x = AIModelRoute(id=str(uuid4()), tenant_id=tenant_id, route_code=route_code, **values); db.add(x)
    _event(db, tenant_id, "ai.model_route.configured", x.id, {"route_code": route_code, "provider_code": provider_code, "model_code": model_code})
    db.commit(); db.refresh(x); return x

def choose_model_route(db: Session, tenant_id: int, request: ModelRouteRequest) -> ModelRouteDecision:
    routes = db.scalars(select(AIModelRoute).where(AIModelRoute.tenant_id == tenant_id, AIModelRoute.enabled.is_(True), AIModelRoute.task_class == request.task_class).order_by(AIModelRoute.priority)).all()
    providers = {x.code: x for x in db.scalars(select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id, AIProviderConfig.enabled.is_(True))).all()}
    for route in routes:
        if route.provider_code not in providers: continue
        policy = route.policy or {}
        allowed_classes = set(policy.get("data_classes", [c.value for c in DataClass]))
        if not all(c.value in allowed_classes for c in request.required_data_classes): continue
        if any(c in {DataClass.SECURITY, DataClass.SECRET} for c in request.required_data_classes):
            if providers[route.provider_code].privacy_class not in {"private", "restricted"}: continue
        if request.requires_structured_output and not route.structured_output: continue
        if request.requires_tool_calling and not route.tool_calling: continue
        return ModelRouteDecision(provider_code=route.provider_code, model_code=route.model_code, route_code=route.route_code, reason="lowest-priority eligible route")
    raise ValueError("no eligible AI model route")


def trace(db: Session, tenant_id: int, run_id: str, stage: str, event_type: str, data: dict, *, redacted: bool = True):
    x = AITraceEvent(id=str(uuid4()), tenant_id=tenant_id, run_id=run_id, stage=stage, event_type=event_type, data=data if redacted else {"redaction_required": True}, redacted=True)
    db.add(x); return x


def record_usage(db: Session, tenant_id: int, run_id: str, *, provider_code: str | None, model_code: str | None,
                 input_tokens: int = 0, output_tokens: int = 0, estimated_cost: Decimal = Decimal("0"), latency_ms: int | None = None,
                 status: str = "completed", metadata: dict | None = None):
    if input_tokens < 0 or output_tokens < 0 or estimated_cost < 0: raise ValueError("AI usage values cannot be negative")
    x = AIUsageEvent(id=str(uuid4()), tenant_id=tenant_id, run_id=run_id, provider_code=provider_code, model_code=model_code,
        input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost=estimated_cost, latency_ms=latency_ms, status=status, metadata_json=metadata or {})
    db.add(x); _event(db, tenant_id, "ai.usage.recorded", x.id, {"run_id": run_id, "status": status}); db.commit(); db.refresh(x); return x
