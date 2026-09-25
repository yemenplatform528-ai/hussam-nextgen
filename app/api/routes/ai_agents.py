"""AI-03 governed multi-agent operations API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.dependencies import get_context, get_session
from app.ai.agents import AgentTask, orchestrate, complete_delegation, ensure_default_agents
from app.core.models.ai_agents import AIAgentRun, AIAgentDelegation
from sqlalchemy import select

router = APIRouter(tags=["ai-agents"])


def developer_guard(ctx):
    if ctx.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="AI agent delegation completion requires owner or admin role")


class AgentTaskIn(BaseModel):
    goal: str = Field(min_length=1, max_length=1000)
    requested_agents: list[str] = []
    market_id: int | None = None
    max_agents: int = Field(default=4, ge=1, le=8)
    max_depth: int = Field(default=2, ge=0, le=3)


@router.get("/ai/agents/registry")
def registry(ctx=Depends(get_context), db=Depends(get_session)):
    rows = ensure_default_agents(db, ctx.tenant_id)
    return {"items": [{"code": x.code, "role": x.role, "enabled": x.enabled,
                       "scopes": x.scopes, "tool_codes": x.tool_codes,
                       "approval_mode": x.approval_mode} for x in rows],
            "orchestration": "bounded", "autonomy": "no_autonomous_mutation"}


@router.post("/ai/agents/orchestrate", status_code=201)
def run_task(body: AgentTaskIn, ctx=Depends(get_context), db=Depends(get_session)):
    return orchestrate(db, ctx.tenant_id, ctx.user_id, AgentTask(**body.model_dump()))


@router.get("/ai/agents/runs/{run_id}")
def run_status(run_id: str, ctx=Depends(get_context), db=Depends(get_session)):
    run = db.scalar(select(AIAgentRun).where(AIAgentRun.id == run_id, AIAgentRun.tenant_id == ctx.tenant_id))
    if not run:
        raise ValueError("agent run not found in tenant")
    delegations = db.scalars(select(AIAgentDelegation).where(
        AIAgentDelegation.run_id == run.id, AIAgentDelegation.tenant_id == ctx.tenant_id).order_by(AIAgentDelegation.sequence)).all()
    return {"run_id": run.id, "status": run.status, "goal": run.goal, "selected_agents": run.selected_agents,
            "delegations": [{"id": d.id, "agent_code": d.child_agent_code, "status": d.status,
                             "depth": d.depth, "scopes": d.allowed_scopes, "result": d.result} for d in delegations]}


@router.post("/ai/agents/delegations/{delegation_id}/complete")
def delegation_complete(delegation_id: str, result: dict, ctx=Depends(get_context), db=Depends(get_session)):
    developer_guard(ctx)
    x = complete_delegation(db, ctx.tenant_id, delegation_id, result)
    return {"id": x.id, "status": x.status, "agent_code": x.child_agent_code}
