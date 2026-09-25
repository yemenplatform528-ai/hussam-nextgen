"""AI-01 control-plane endpoints. Secrets and provider credentials never cross this API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.api.dependencies import get_context, get_session
from app.core.models.ai_foundation import AIProviderConfig, AIModelRoute, AIAgentDefinition, AIMemoryRecord
from app.ai.contracts import AgentContract, DataClass, MemoryType, ModelRouteRequest, ToolContract
from app.ai.foundation import register_provider, register_model_route, register_agent, register_tool_contract, remember, revoke_memory, choose_model_route
from app.ai.policy import authorize_tool
from app.core.models.ai_hus import AIToolDefinition

router = APIRouter(tags=["ai-foundation"])


def developer_guard(ctx):
    if ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="AI foundation control plane requires owner or admin role")

class ProviderIn(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    provider_kind: str = Field(min_length=1, max_length=40)
    endpoint_ref: str | None = None
    credential_ref: str | None = None
    privacy_class: str = "standard"
    enabled: bool = False

class RouteIn(BaseModel):
    route_code: str
    provider_code: str
    model_code: str
    task_class: str
    priority: int = 100
    max_input_tokens: int | None = None
    structured_output: bool = False
    tool_calling: bool = False
    policy: dict = {}

class AgentIn(BaseModel):
    code: str
    role: str
    scopes: list[str]
    tool_codes: list[str] = []
    data_classes: list[DataClass] = []
    risk_class: str = "low"
    approval_mode: str = "human_required"
    system_policy: str = Field(min_length=1, max_length=10000)

class MemoryIn(BaseModel):
    memory_type: MemoryType
    key: str = Field(min_length=1, max_length=180)
    value: dict
    source: str = Field(min_length=1, max_length=40)
    owner_id: str | None = None
    agent_code: str | None = None
    trust: str = "unverified"
    ttl_seconds: int | None = None

class ToolContractIn(BaseModel):
    code: str
    description: str
    action_class: str
    risk_class: str = "low"
    data_classes: list[DataClass] = []
    requires_approval: bool = True
    idempotent: bool = False
    input_schema: dict = {}
    handler_key: str | None = None

class RouteRequestIn(BaseModel):
    task_class: str
    required_data_classes: list[DataClass] = []
    requires_structured_output: bool = False
    requires_tool_calling: bool = False

@router.post("/ai/foundation/providers", status_code=201)
def provider(body: ProviderIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x = register_provider(db, ctx.tenant_id, **body.model_dump())
    return {"id": x.id, "code": x.code, "provider_kind": x.provider_kind, "enabled": x.enabled, "privacy_class": x.privacy_class}

@router.get("/ai/foundation/providers")
def providers(ctx=Depends(get_context), db=Depends(get_session)):
    rows = db.scalars(select(AIProviderConfig).where(AIProviderConfig.tenant_id == ctx.tenant_id).order_by(AIProviderConfig.code)).all()
    return {"items": [{"code": x.code, "provider_kind": x.provider_kind, "enabled": x.enabled, "privacy_class": x.privacy_class, "credential_ref": x.credential_ref} for x in rows]}

@router.post("/ai/foundation/routes", status_code=201)
def route(body: RouteIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x = register_model_route(db, ctx.tenant_id, **body.model_dump())
    return {"id": x.id, "route_code": x.route_code, "provider_code": x.provider_code, "model_code": x.model_code, "task_class": x.task_class}

@router.post("/ai/foundation/routes/select")
def select_route(body: RouteRequestIn, ctx=Depends(get_context), db=Depends(get_session)):
    return choose_model_route(db, ctx.tenant_id, ModelRouteRequest(**body.model_dump())).model_dump()

@router.post("/ai/foundation/tools", status_code=201)
def tool(body: ToolContractIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    from app.ai.contracts import ActionClass
    try: action_class = ActionClass(body.action_class)
    except ValueError: raise ValueError("invalid AI action class")
    contract = ToolContract(code=body.code, description=body.description, action_class=action_class, risk_class=body.risk_class,
                            data_classes=body.data_classes, requires_approval=body.requires_approval, idempotent=body.idempotent, input_schema=body.input_schema)
    x = register_tool_contract(db, ctx.tenant_id, contract, handler_key=body.handler_key)
    return {"id": x.id, "code": x.code, "risk": x.risk, "side_effect_class": x.side_effect_class, "approval_required": x.approval_required}

@router.post("/ai/foundation/agents", status_code=201)
def agent(body: AgentIn, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    contract = AgentContract(code=body.code, role=body.role, scopes=body.scopes, tool_codes=body.tool_codes,
                             data_classes=body.data_classes, risk_class=body.risk_class, approval_mode=body.approval_mode)
    x = register_agent(db, ctx.tenant_id, contract, body.system_policy)
    return {"id": x.id, "code": x.code, "role": x.role, "scopes": x.scopes, "tool_codes": x.tool_codes, "approval_mode": x.approval_mode}

@router.get("/ai/foundation/agents")
def agents(ctx=Depends(get_context), db=Depends(get_session)):
    rows = db.scalars(select(AIAgentDefinition).where(AIAgentDefinition.tenant_id == ctx.tenant_id).order_by(AIAgentDefinition.code)).all()
    return {"items": [{"code": x.code, "role": x.role, "enabled": x.enabled, "scopes": x.scopes, "tool_codes": x.tool_codes, "data_classes": x.data_classes, "approval_mode": x.approval_mode} for x in rows]}

@router.post("/ai/foundation/memory", status_code=201)
def memory(body: MemoryIn, ctx=Depends(get_context), db=Depends(get_session)):
    payload = body.model_dump()
    if body.memory_type == MemoryType.USER_PREFERENCE:
        payload["owner_id"] = ctx.user_id
    x = remember(db, ctx.tenant_id, **payload)
    return {"id": x.id, "memory_type": x.memory_type, "key": x.key, "owner_id": x.owner_id, "agent_code": x.agent_code, "revocable": x.revocable}

@router.post("/ai/foundation/memory/{memory_id}/revoke")
def revoke(memory_id: str, ctx=Depends(get_context), db=Depends(get_session)):
    memory = db.scalar(select(AIMemoryRecord).where(AIMemoryRecord.id == memory_id, AIMemoryRecord.tenant_id == ctx.tenant_id))
    if not memory:
        raise HTTPException(status_code=404, detail="AI memory not found in tenant")
    if ctx.role not in {"owner", "admin"} and memory.owner_id != ctx.user_id:
        raise HTTPException(status_code=403, detail="AI memory can only be revoked by its owner or an administrator")
    x = revoke_memory(db, ctx.tenant_id, memory_id)
    return {"id": x.id, "revoked_at": x.revoked_at.isoformat()}

@router.get("/ai/foundation/status")
def status(ctx=Depends(get_context), db=Depends(get_session)):
    providers = len(db.scalars(select(AIProviderConfig).where(AIProviderConfig.tenant_id == ctx.tenant_id)).all())
    routes = len(db.scalars(select(AIModelRoute).where(AIModelRoute.tenant_id == ctx.tenant_id, AIModelRoute.enabled.is_(True))).all())
    agents = len(db.scalars(select(AIAgentDefinition).where(AIAgentDefinition.tenant_id == ctx.tenant_id, AIAgentDefinition.enabled.is_(True))).all())
    return {"ai_01": "locked", "providers": providers, "enabled_routes": routes, "enabled_agents": agents,
            "security_boundary": "deterministic_core_policy", "execution_mode": "governed"}
