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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.amazon_completion import HUSExecutionRecord
from app.core.models.ai_hus import HUSCompilation
from app.ai.foundation import trace as record_ai_trace
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
    arguments_hash: str | None = None


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


def _existing_replay(db: Session, ctx: RuntimeContext) -> HUSExecutionRecord | None:
    replay = db.scalar(select(HUSExecutionRecord).where(
        HUSExecutionRecord.tenant_id == ctx.tenant_id,
        HUSExecutionRecord.compilation_id == ctx.compilation_id,
        HUSExecutionRecord.idempotency_key == ctx.idempotency_key,
        HUSExecutionRecord.actor_id == ctx.actor_id,
        HUSExecutionRecord.action == ctx.action,
    ))
    if replay is None:
        return None
    payload = replay.input_json or {}
    if payload.get("step_id") != ctx.step_id or payload.get("plan_hash") != ctx.plan_hash:
        raise HUSRuntimeError("idempotency key is bound to a different execution intent")
    return replay


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
        arguments_hash = _hash(arguments)
        ctx = RuntimeContext(**{**ctx.__dict__, "arguments_hash": arguments_hash})
        if not ctx.idempotency_key and idempotency_key:
            ctx = RuntimeContext(**{**ctx.__dict__, "idempotency_key": idempotency_key})
        read = _is_read(ctx.action)
        if not read and not approved:
            raise HUSRuntimeError("mutation execution requires explicit approval")
        if not read:
            if self._approval_verifier is None:
                raise HUSRuntimeError("mutation approval verifier is not configured")
            if not self._approval_verifier(self.db, ctx):
                raise HUSRuntimeError("approval evidence is invalid or expired")
        if not read and not ctx.idempotency_key:
            raise HUSRuntimeError("mutation execution requires an idempotency key")

        trace_run_id = f"hus-exec:{ctx.compilation_id}:{ctx.step_id}"
        if ctx.approval_ref:
            from app.core.models.ai_hus import AIAction
            approved_action = self.db.get(AIAction, ctx.approval_ref)
            if approved_action and approved_action.run_id:
                trace_run_id = approved_action.run_id

        if ctx.idempotency_key:
            replay = _existing_replay(self.db, ctx)
            if replay:
                prior_hash = (replay.input_json or {}).get("arguments_hash")
                if prior_hash != arguments_hash:
                    raise HUSRuntimeError("idempotency key was already used with different arguments")
                record_ai_trace(
                    self.db, ctx.tenant_id, trace_run_id, "VERIFICATION", "HUS_EXECUTION_REPLAY",
                    {"execution_id": replay.id, "action": ctx.action, "idempotency_key": ctx.idempotency_key, "result": replay.status},
                )
                self.db.commit()
                return RuntimeResult(replay.id, replay.status, replay.output_json, replayed=True)

        now = datetime.now(timezone.utc)
        payload = {"arguments": arguments, "arguments_hash": arguments_hash, "idempotency_key": ctx.idempotency_key, "plan_hash": ctx.plan_hash, "step_id": ctx.step_id}
        rec = HUSExecutionRecord(
            tenant_id=ctx.tenant_id,
            compilation_id=ctx.compilation_id,
            actor_id=ctx.actor_id,
            action=ctx.action,
            idempotency_key=ctx.idempotency_key,
            status="approved" if approved else "authorized",
            input_json=payload,
            approval_ref=ctx.approval_ref,
        )
        try:
            with self.db.begin_nested():
                self.db.add(rec)
                self.db.flush()
        except IntegrityError:
            replay = self.db.scalar(select(HUSExecutionRecord).where(
                HUSExecutionRecord.tenant_id == ctx.tenant_id,
                HUSExecutionRecord.compilation_id == ctx.compilation_id,
                HUSExecutionRecord.idempotency_key == ctx.idempotency_key,
            ))
            if replay is None:
                raise
            payload = replay.input_json or {}
            if replay.actor_id != ctx.actor_id or replay.action != ctx.action or payload.get("step_id") != ctx.step_id or payload.get("plan_hash") != ctx.plan_hash:
                raise HUSRuntimeError("idempotency key is bound to a different execution intent")
            prior_hash = payload.get("arguments_hash")
            if prior_hash != arguments_hash:
                raise HUSRuntimeError("idempotency key was already used with different arguments")
            record_ai_trace(
                self.db, ctx.tenant_id, trace_run_id, "VERIFICATION", "HUS_EXECUTION_REPLAY",
                {"execution_id": replay.id, "action": ctx.action, "idempotency_key": ctx.idempotency_key, "result": replay.status, "race_recovered": True},
            )
            self.db.commit()
            return RuntimeResult(replay.id, replay.status, replay.output_json, replayed=True)
        execution_id = rec.id
        record_ai_trace(
            self.db, ctx.tenant_id, trace_run_id, "ACTION", "HUS_EXECUTION_STARTED",
            {"execution_id": execution_id, "action": ctx.action, "step_id": ctx.step_id, "idempotency_key": ctx.idempotency_key},
        )
        rec.status = "running"
        try:
            handler = (self._handlers if read else self._mutation_handlers).get(ctx.action)
            if handler is None:
                raise HUSRuntimeError("no sovereign runtime handler is registered for this capability")
            with self.db.begin_nested():
                out = handler(self.db, ctx, arguments)
                if not isinstance(out, dict):
                    raise HUSRuntimeError("runtime handler must return an object")
                rec.output_json = {
                    "result": out,
                    "provenance": {"plan_hash": ctx.plan_hash, "step_id": ctx.step_id, "actor_id": ctx.actor_id},
                    "verification": {"status": "PASS", "method": "handler-result-type-and-transaction-commit"},
                    "evidence": {"execution_id": execution_id, "observed_status": "completed", "observed_output_hash": _hash(out)},
                }
                rec.status = "completed"
                rec.completed_at = now
                record_ai_trace(
                    self.db, ctx.tenant_id, trace_run_id, "OBSERVATION", "HUS_EXECUTION_OBSERVED",
                    {"execution_id": execution_id, "status": "completed", "output_hash": _hash(out)},
                )
                record_ai_trace(
                    self.db, ctx.tenant_id, trace_run_id, "VERIFICATION", "HUS_EXECUTION_VERIFIED",
                    {"execution_id": execution_id, "result": "PASS", "method": "handler-result-type-and-transaction-commit"},
                )
                record_ai_trace(
                    self.db, ctx.tenant_id, trace_run_id, "EVIDENCE", "HUS_EXECUTION_EVIDENCE",
                    {"execution_id": execution_id, "status": "completed", "output_hash": _hash(out), "evidence_level": "L2_REPRODUCED"},
                )
            self.db.commit()
            return RuntimeResult(execution_id, "completed", rec.output_json)
        except Exception as exc:
            # The execution record is created before the domain handler. Keep that
            # durable record and mark it failed; do not insert a second row with
            # the same idempotency identity after the handler transaction rolls back.
            rec.status = "failed"
            rec.output_json = {
                "error": str(exc),
                "provenance": {"plan_hash": ctx.plan_hash, "step_id": ctx.step_id, "actor_id": ctx.actor_id},
                "verification": {"status": "FAIL", "method": "exception-observed"},
                "evidence": {"execution_id": execution_id, "observed_status": "failed", "success_claim": False},
            }
            rec.completed_at = datetime.now(timezone.utc)
            record_ai_trace(
                self.db, ctx.tenant_id, trace_run_id, "OBSERVATION", "HUS_EXECUTION_OBSERVED",
                {"execution_id": execution_id, "status": "failed", "error_class": type(exc).__name__},
            )
            record_ai_trace(
                self.db, ctx.tenant_id, trace_run_id, "VERIFICATION", "HUS_EXECUTION_VERIFICATION_FAILED",
                {"execution_id": execution_id, "result": "FAIL", "method": "exception-observed"},
            )
            record_ai_trace(
                self.db, ctx.tenant_id, trace_run_id, "EVIDENCE", "HUS_EXECUTION_NO_SUCCESS_EVIDENCE",
                {"execution_id": execution_id, "status": "failed", "success_claim": False},
            )
            self.db.commit()
            if isinstance(exc, HUSRuntimeError):
                raise
            raise HUSRuntimeError("HUS runtime handler failed") from exc

    def execute_step(self, tenant_id: int, actor_id: str, compilation_id: str, step_id: str, arguments: dict, *, approval_ref: str | None = None, approved: bool = False, idempotency_key: str | None = None) -> RuntimeResult:
        ctx = self.authorize(tenant_id, actor_id, compilation_id, step_id, approval_ref=approval_ref)
        return self.execute(ctx, arguments, approved=approved, idempotency_key=idempotency_key)
