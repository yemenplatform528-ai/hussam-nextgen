"""AI-04: product safety, evaluation, failover evidence and Control Center boundary."""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.ai_product import AIProviderHealthCheck, AIEvaluationSuite, AIEvaluationResult, AIReleaseGate, AIControlChange
from app.core.models.ai_foundation import AIProviderConfig, AIModelRoute, AIMemoryRecord, AIAgentDefinition
from app.core.models.ai_hus import AIToolDefinition
from app.core.models.governance import OutboxEvent


def _now(): return datetime.now(timezone.utc)

def _event(db, tenant_id, typ, aggregate_id, payload):
    db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=typ, aggregate_type="ai_product", aggregate_id=str(aggregate_id), payload=payload, published=False))


def record_provider_health(db: Session, tenant_id: int, provider_code: str, *, status: str, latency_ms: int | None = None, error_class: str | None = None, evidence: dict | None = None):
    if status not in {"healthy", "degraded", "unavailable", "blocked"}:
        raise ValueError("invalid provider health status")
    provider = db.scalar(select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id, AIProviderConfig.code == provider_code))
    if not provider:
        raise ValueError("provider not found in tenant")
    if latency_ms is not None and latency_ms < 0:
        raise ValueError("latency cannot be negative")
    x = AIProviderHealthCheck(id=str(uuid4()), tenant_id=tenant_id, provider_code=provider_code, status=status, latency_ms=latency_ms, error_class=error_class, evidence=evidence or {}, checked_at=_now())
    db.add(x); _event(db, tenant_id, "ai.provider.health_checked", x.id, {"provider_code": provider_code, "status": status}); db.commit(); db.refresh(x); return x


def register_evaluation_suite(db: Session, tenant_id: int, code: str, version: str, checks: list[str], threshold: Decimal = Decimal("0.90")):
    if not checks: raise ValueError("evaluation suite requires checks")
    if threshold < 0 or threshold > 1: raise ValueError("evaluation threshold must be between 0 and 1")
    x = db.scalar(select(AIEvaluationSuite).where(AIEvaluationSuite.tenant_id == tenant_id, AIEvaluationSuite.code == code))
    if x:
        x.version, x.checks, x.threshold, x.enabled = version, list(dict.fromkeys(checks)), threshold, True
    else:
        x = AIEvaluationSuite(id=str(uuid4()), tenant_id=tenant_id, code=code, version=version, checks=list(dict.fromkeys(checks)), threshold=threshold, enabled=True); db.add(x)
    _event(db, tenant_id, "ai.evaluation_suite.configured", x.id, {"code": code, "version": version}); db.commit(); db.refresh(x); return x


def record_evaluation_result(db: Session, tenant_id: int, suite_code: str, run_id: str, metric: str, score: Decimal, evidence: dict | None = None):
    if score < 0 or score > 1: raise ValueError("evaluation score must be between 0 and 1")
    suite = db.scalar(select(AIEvaluationSuite).where(AIEvaluationSuite.tenant_id == tenant_id, AIEvaluationSuite.code == suite_code, AIEvaluationSuite.enabled.is_(True)))
    if not suite: raise ValueError("evaluation suite not enabled in tenant")
    x = AIEvaluationResult(id=str(uuid4()), tenant_id=tenant_id, suite_code=suite_code, run_id=run_id, metric=metric, score=score, passed=score >= suite.threshold, evidence=evidence or {})
    db.add(x); _event(db, tenant_id, "ai.evaluation.result_recorded", x.id, {"suite_code": suite_code, "metric": metric, "passed": x.passed}); db.commit(); db.refresh(x); return x


def build_release_gate(db: Session, tenant_id: int, release_code: str, required_checks: list[str], evidence: dict | None = None):
    required = list(dict.fromkeys(required_checks))
    if not required: raise ValueError("release gate requires checks")
    results = db.scalars(select(AIEvaluationResult).where(AIEvaluationResult.tenant_id == tenant_id).order_by(AIEvaluationResult.created_at.desc())).all()
    passed = []
    latest = {}
    for r in results:
        if r.metric not in latest: latest[r.metric] = r
    for check in required:
        r = latest.get(check)
        if r and r.passed: passed.append(check)
    missing = [x for x in required if x not in passed]
    x = db.scalar(select(AIReleaseGate).where(AIReleaseGate.tenant_id == tenant_id, AIReleaseGate.release_code == release_code))
    status = "ready" if not missing else "blocked"
    if x:
        x.status, x.required_checks, x.passed_checks, x.evidence, x.blocked_reason, x.updated_at = status, required, passed, evidence or {}, (None if not missing else "missing or failed checks: " + ", ".join(missing)), _now()
    else:
        x = AIReleaseGate(id=str(uuid4()), tenant_id=tenant_id, release_code=release_code, status=status, required_checks=required, passed_checks=passed, evidence=evidence or {}, blocked_reason=(None if not missing else "missing or failed checks: " + ", ".join(missing)), updated_at=_now()); db.add(x)
    _event(db, tenant_id, "ai.release_gate.evaluated", x.id, {"release_code": release_code, "status": status, "missing": missing}); db.commit(); db.refresh(x); return x


def control_change(db: Session, tenant_id: int, actor_id: str, *, resource_type: str, resource_code: str, action: str, before_state: dict, after_state: dict):
    """Record bounded Control Center changes; secrets and domain truth are never accepted as state."""
    if resource_type not in {"provider", "model_route", "agent", "tool", "evaluation_suite"}:
        raise ValueError("resource type is outside AI Control Center boundary")
    forbidden = {"secret", "password", "token", "api_key", "private_key", "sql", "database"}
    keys = {str(k).lower() for k in after_state}
    if any(any(term in key for term in forbidden) for key in keys):
        raise ValueError("secret or direct database state cannot be changed through AI Control Center")
    x = AIControlChange(id=str(uuid4()), tenant_id=tenant_id, actor_id=actor_id, resource_type=resource_type, resource_code=resource_code, action=action, before_state=before_state, after_state=after_state, status="applied")
    db.add(x); _event(db, tenant_id, "ai.control.changed", x.id, {"resource_type": resource_type, "resource_code": resource_code, "action": action}); db.commit(); db.refresh(x); return x


def security_release_snapshot(db: Session, tenant_id: int) -> dict:
    providers = db.scalars(select(AIProviderConfig).where(AIProviderConfig.tenant_id == tenant_id)).all()
    routes = db.scalars(select(AIModelRoute).where(AIModelRoute.tenant_id == tenant_id)).all()
    agents = db.scalars(select(AIAgentDefinition).where(AIAgentDefinition.tenant_id == tenant_id)).all()
    tools = db.scalars(select(AIToolDefinition).where(AIToolDefinition.tenant_id == tenant_id)).all()
    memory = db.scalars(select(AIMemoryRecord).where(AIMemoryRecord.tenant_id == tenant_id, AIMemoryRecord.revoked_at.is_(None))).all()
    return {
        "tenant_id": tenant_id,
        "providers": {"count": len(providers), "enabled": sum(1 for x in providers if x.enabled)},
        "routes": {"count": len(routes), "enabled": sum(1 for x in routes if x.enabled)},
        "agents": {"count": len(agents), "enabled": sum(1 for x in agents if x.enabled)},
        "tools": {"count": len(tools), "enabled": sum(1 for x in tools if x.enabled), "mutation_tools_require_approval": all((not x.approval_required) or x.side_effect_class in {"read", "analyze", "propose", "confirm", "execute"} for x in tools)},
        "active_memory_records": len(memory),
        "principle": "AI is governed intelligence; Core remains authoritative",
    }
