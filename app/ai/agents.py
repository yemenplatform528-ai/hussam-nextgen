"""AI-03 governed multi-agent orchestration.

Agents are identities with bounded scopes. The orchestrator may delegate analysis,
but it cannot grant permissions, execute mutations, or bypass Core authority.
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.core.models.ai_agents import AIAgentRun, AIAgentDelegation
from app.core.models.ai_foundation import AIAgentDefinition
from app.ai.contracts import AgentContract, DataClass, ActionClass
from app.ai.foundation import register_agent
from app.ai.policy import authorize_tool


def _now():
    return datetime.now(timezone.utc)


class AgentTask(BaseModel):
    goal: str = Field(min_length=1, max_length=1000)
    requested_agents: list[str] = Field(default_factory=list)
    market_id: int | None = None
    max_agents: int = Field(default=4, ge=1, le=8)
    max_depth: int = Field(default=2, ge=0, le=3)


DEFAULT_AGENTS = {
    "customer_commerce_assistant": AgentContract(
        code="customer_commerce_assistant", role="customer_commerce", scopes=["marketplace.customer.read"],
        tool_codes=["marketplace.customer.context", "marketplace.catalog.read"],
        data_classes=[DataClass.PUBLIC, DataClass.TENANT, DataClass.PERSONAL], risk_class="low", approval_mode="human_required"),
    "seller_operations_assistant": AgentContract(
        code="seller_operations_assistant", role="seller_operations", scopes=["marketplace.seller.read", "marketplace.seller.propose"],
        tool_codes=["marketplace.seller.intelligence", "marketplace.commerce_review"],
        data_classes=[DataClass.TENANT], risk_class="medium", approval_mode="human_required"),
    "marketplace_operations_assistant": AgentContract(
        code="marketplace_operations_assistant", role="marketplace_operations", scopes=["marketplace.operations.read", "marketplace.operations.propose"],
        tool_codes=["marketplace.operations.snapshot", "marketplace.commerce_review"],
        data_classes=[DataClass.PUBLIC, DataClass.TENANT], risk_class="medium", approval_mode="human_required"),
    "finance_assistant": AgentContract(
        code="finance_assistant", role="finance_read_only", scopes=["finance.read"],
        tool_codes=["platform.business_snapshot"], data_classes=[DataClass.TENANT, DataClass.FINANCIAL],
        risk_class="medium", approval_mode="human_required"),
    "risk_trust_assistant": AgentContract(
        code="risk_trust_assistant", role="risk_trust", scopes=["trust.read", "trust.propose"],
        tool_codes=["platform.business_snapshot"], data_classes=[DataClass.TENANT, DataClass.PERSONAL],
        risk_class="high", approval_mode="human_required"),
}


def ensure_default_agents(db: Session, tenant_id: int) -> list[AIAgentDefinition]:
    rows = []
    for contract in DEFAULT_AGENTS.values():
        existing = db.scalar(select(AIAgentDefinition).where(
            AIAgentDefinition.tenant_id == tenant_id, AIAgentDefinition.code == contract.code))
        if existing:
            rows.append(existing)
            continue
        rows.append(register_agent(
            db, tenant_id, contract,
            "Agent identity is bounded by explicit scope, tool grants, data classes and approval policy. "
            "It cannot execute domain mutations outside the governed tool gateway."))
    return rows


def _matching_agents(goal: str, requested: list[str], max_agents: int) -> list[str]:
    if requested:
        return list(dict.fromkeys(requested))[:max_agents]
    text = goal.lower()
    selected = []
    if any(k in text for k in ("customer", "buyer", "recommend", "product", "search")):
        selected.append("customer_commerce_assistant")
    if any(k in text for k in ("seller", "listing", "sales", "catalog")):
        selected.append("seller_operations_assistant")
    if any(k in text for k in ("marketplace", "operations", "order", "fulfillment")):
        selected.append("marketplace_operations_assistant")
    if any(k in text for k in ("finance", "payment", "settlement", "payout", "accounting")):
        selected.append("finance_assistant")
    if any(k in text for k in ("risk", "trust", "fraud", "dispute")):
        selected.append("risk_trust_assistant")
    return list(dict.fromkeys(selected or ["marketplace_operations_assistant"]))[:max_agents]


def orchestrate(db: Session, tenant_id: int, actor_id: str, task: AgentTask) -> dict:
    if task.max_depth > 2:
        raise ValueError("agent delegation depth exceeds platform limit")
    agents = ensure_default_agents(db, tenant_id)
    by_code = {a.code: a for a in agents}
    selected = _matching_agents(task.goal, task.requested_agents, task.max_agents)
    unknown = [code for code in selected if code not in by_code or not by_code[code].enabled]
    if unknown:
        raise ValueError(f"agent not enabled in tenant: {unknown[0]}")

    run = AIAgentRun(id=str(uuid4()), tenant_id=tenant_id, actor_id=actor_id, goal=task.goal,
                     market_id=task.market_id, status="planned", depth=0, budget_agents=task.max_agents,
                     selected_agents=selected, result={"mode": "bounded_delegation"})
    db.add(run)
    db.flush()

    delegations = []
    for idx, code in enumerate(selected, start=1):
        agent = by_code[code]
        delegation = AIAgentDelegation(
            id=str(uuid4()), tenant_id=tenant_id, run_id=run.id, parent_agent_code="platform_orchestrator",
            child_agent_code=code, sequence=idx, depth=1, goal=task.goal, market_id=task.market_id,
            allowed_scopes=list(agent.scopes), status="planned")
        db.add(delegation)
        delegations.append(delegation)

    run.status = "delegated"
    run.result = {
        "execution_mode": "analysis_and_proposal_only",
        "selected_agents": selected,
        "delegations": [
            {"id": d.id, "agent_code": d.child_agent_code, "scopes": d.allowed_scopes,
             "depth": d.depth, "status": d.status}
            for d in delegations
        ],
        "authorization": "each agent retains its own identity and grants; orchestrator cannot escalate them",
        "mutation_policy": "no autonomous mutation; governed approval required",
    }
    db.commit()
    return {"run_id": run.id, "status": run.status, "goal": run.goal,
            "selected_agents": selected, "delegations": run.result["delegations"],
            "execution_policy": "delegation_only; Core authorization remains authoritative"}


def complete_delegation(db: Session, tenant_id: int, delegation_id: str, result: dict, *, status: str = "completed"):
    delegation = db.scalar(select(AIAgentDelegation).where(
        AIAgentDelegation.id == delegation_id, AIAgentDelegation.tenant_id == tenant_id))
    if not delegation:
        raise ValueError("delegation not found in tenant")
    if status not in {"completed", "failed", "blocked"}:
        raise ValueError("invalid delegation completion status")
    delegation.status = status
    delegation.result = result
    db.commit()
    return delegation
