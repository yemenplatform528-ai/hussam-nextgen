"""HUS-03 sovereign runtime boundary.

The runtime accepts only compiled, active execution plans. It never executes HUS source,
Python, SQL, shell, arbitrary URLs, or model-generated code. Domain mutations require
explicit approval and an idempotency key. Actual business effects are delegated to
allow-listed domain handlers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models.amazon_completion import HUSExecutionRecord
from app.core.models.ai_hus import HUSCompilation
from .registry import capabilities_for

READ_SUFFIXES = {"read"}
TERMINAL = {"completed", "failed", "rejected", "cancelled"}
ALLOWED_STATUS = {"planned", "authorized", "waiting_approval", "approved", "running", *TERMINAL}


class HUSRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeContext:
    tenant_id: int
    actor_id: str
    compilation_id: str
    plan_hash: str
    step_id: str
    action: str
    approval_ref: str | None
    idempotency_key: str | None


@dataclass(frozen=True)
class RuntimeResult:
    execution_id: int
    status: str
    output: dict | None
    replayed: bool = False


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: object) -> str:
    return sha256(_canonical(value).encode()).hexdigest()


def _is_read(action: str) -> bool:
    _, cap = action.split(".", 1)
    return cap == "read" or cap.endswith(".read")


def _registered(action: str) -> bool:
    if "." not in action:
        return False
    engine, cap = action.split(".", 1)
    return engine in {"retail", "inventory", "commerce", "procurement", "payments", "logistics", "finance", "workflow", "documents", "marketplace", "custom"} and any(c == cap or c.endswith("." + cap) for c in capabilities_for(engine))


def _plan_steps(compilation: HUSCompilation) -> dict[str, dict]:
    plan = (compilation.contract or {}).get("execution_plan") or (compilation.contract or {}).get("ir")
    if not isinstance(plan, dict):
        raise HUSRuntimeError("compiled HUS execution plan is missing")
    steps = {}
    for workflow in plan.get("workflows", []):
        for step in workflow.get("steps", []):
            if isinstance(step, dict) and step.get("id"):
                steps[step["id"]] = step
    return steps


def _active_compilation(db: Session, tenant_id: int, compilation_id: str) -> HUSCompilation:
    x = db.scalar(select(HUSCompilation).where(HUSCompilation.id == compilation_id, HUSCompilation.tenant_id == tenant_id))
    if not x or x.status != "active":
        raise HUSRuntimeError("active HUS compilation not found in tenant")
    return x


def _existing_replay(db: Session, tenant_id: int, compilation_id: str, idempotency_key: str) -> HUSExecutionRecord | None:
    rows = db.scalars(select(HUSExecutionRecord).where(
        HUSExecutionRecord.tenant_id == tenant_id,
        HUSExecutionRecord.compilation_id == compilation_id,
    )).all()
    for row in rows:
        if isinstance(row.input_json, dict) and row.input_json.get("idempotency_key") == idempotency_key:
            return row
    return None


class SovereignRuntime:
    """Fail-closed runtime for bounded HUS execution plans."""

    def __init__(self, db: Session):
        self.db = db
        self._handlers: dict[str, Callable[[Session, RuntimeContext, dict], dict]] = {}
        self._mutation_handlers: dict[str, Callable[[Session, RuntimeContext, dict], dict]] = {}
        self._approval_verifier: Callable[[Session, RuntimeContext], bool] | None = None

    def register_mutation_handler(self, action: str, handler: Callable[[Session, RuntimeContext, dict], dict]) -> None:
        if not _registered(action) or _is_read(action):
            raise HUSRuntimeError("only registered mutation capabilities may be bound as runtime handlers")
        self._mutation_handlers[action] = handler

    def configure_approval_verifier(self, verifier: Callable[[Session, RuntimeContext], bool]) -> None:
        self._approval_verifier = verifier

    def register_read_handler(self, action: str, handler: Callable[[Session, RuntimeContext, dict], dict]) -> None:
        if not _registered(action) or not _is_read(action):
            raise HUSRuntimeError("only registered read capabilities may be bound as runtime handlers")
        self._handlers[action] = handler

    def authorize(self, tenant_id: int, actor_id: str, compilation_id: str, step_id: str, *, approval_ref: str | None = None) -> RuntimeContext:
        compilation = _active_compilation(self.db, tenant_id, compilation_id)
        steps = _plan_steps(compilation)
        step = steps.get(step_id)
        if not step:
            raise HUSRuntimeError("HUS execution step is not present in the active plan")
        action_obj = step.get("action") or {}
        action = f"{action_obj.get('engine')}.{action_obj.get('capability')}"
        if not _registered(action):
            raise HUSRuntimeError("HUS capability is not registered")
        if step.get("risk") != "read" and not step.get("idempotency_required", False):
            raise HUSRuntimeError("mutation plan step must require idempotency")
        if step.get("risk") != "read" and not approval_ref:
            raise HUSRuntimeError("mutation execution requires an approval reference")
        plan_hash = compilation.contract_hash or _hash(compilation.contract or {})
        return RuntimeContext(tenant_id, actor_id, compilation_id, plan_hash, step_id, action, approval_ref, None)

    def execute(self, ctx: RuntimeContext, arguments: dict, *, idempotency_key: str | None = None, approved: bool = False) -> RuntimeResult:
        if not isinstance(arguments, dict):
            raise HUSRuntimeError("arguments must be an object")
        if not ctx.idempotency_key and idempotency_key:
            ctx = RuntimeContext(**{**ctx.__dict__, "idempotency_key": idempotency_key})
        read = _is_read(ctx.action)
        if not read and not approved:
            raise HUSRuntimeError("mutation execution requires explicit approval")
        if not read and self._approval_verifier is not None and not self._approval_verifier(self.db, ctx):
            raise HUSRuntimeError("approval evidence is invalid or expired")
        if not read and not ctx.idempotency_key:
            raise HUSRuntimeError("mutation execution requires an idempotency key")
        if ctx.idempotency_key:
            replay = _existing_replay(self.db, ctx.tenant_id, ctx.compilation_id, ctx.idempotency_key)
            if replay:
                return RuntimeResult(replay.id, replay.status, replay.output_json, replayed=True)

        now = datetime.now(timezone.utc)
        payload = {"arguments": arguments, "idempotency_key": ctx.idempotency_key, "plan_hash": ctx.plan_hash, "step_id": ctx.step_id}
        rec = HUSExecutionRecord(
            tenant_id=ctx.tenant_id,
            compilation_id=ctx.compilation_id,
            actor_id=ctx.actor_id,
            action=ctx.action,
            status="approved" if approved else "authorized",
            input_json=payload,
            approval_ref=ctx.approval_ref,
        )
        self.db.add(rec)
        self.db.flush()
        execution_id = rec.id
        rec.status = "running"
        try:
            handler = (self._handlers if read else self._mutation_handlers).get(ctx.action)
            if handler is None:
                raise HUSRuntimeError("no sovereign runtime handler is registered for this capability")
            # Domain handlers participate in the same transaction. A handler failure must
            # roll back any flushed business changes; a failed execution record is persisted
            # only after the business transaction is safely rolled back.
            with self.db.begin_nested():
                out = handler(self.db, ctx, arguments)
                if not isinstance(out, dict):
                    raise HUSRuntimeError("runtime handler must return an object")
                rec.output_json = {"result": out, "provenance": {"plan_hash": ctx.plan_hash, "step_id": ctx.step_id, "actor_id": ctx.actor_id}}
                rec.status = "completed"
                rec.completed_at = now
            self.db.commit()
            return RuntimeResult(execution_id, "completed", rec.output_json)
        except Exception as exc:
            self.db.rollback()
            failed = HUSExecutionRecord(
                tenant_id=ctx.tenant_id,
                compilation_id=ctx.compilation_id,
                actor_id=ctx.actor_id,
                action=ctx.action,
                status="failed",
                input_json=payload,
                output_json={"error": str(exc), "provenance": {"plan_hash": ctx.plan_hash, "step_id": ctx.step_id, "actor_id": ctx.actor_id}},
                approval_ref=ctx.approval_ref,
                completed_at=datetime.now(timezone.utc),
            )
            self.db.add(failed)
            self.db.commit()
            if isinstance(exc, HUSRuntimeError):
                raise
            raise HUSRuntimeError("HUS runtime handler failed") from exc

    def execute_step(self, tenant_id: int, actor_id: str, compilation_id: str, step_id: str, arguments: dict, *, approval_ref: str | None = None, approved: bool = False, idempotency_key: str | None = None) -> RuntimeResult:
        ctx = self.authorize(tenant_id, actor_id, compilation_id, step_id, approval_ref=approval_ref)
        return self.execute(ctx, arguments, approved=approved, idempotency_key=idempotency_key)
