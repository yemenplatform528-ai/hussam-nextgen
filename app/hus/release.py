"""HUS final product-lock checks: deterministic, bounded, provenance-aware release gates."""
from __future__ import annotations
from dataclasses import dataclass
from .planner import HUSIR, canonical_ir, plan_hash, validate_ir, MAX_STEPS, MAX_TIMEOUT, MAX_RETRIES

@dataclass(frozen=True)
class HUSReleaseReport:
    deterministic: bool
    bounded: bool
    provenance_ready: bool
    fail_closed: bool
    passed: bool


def evaluate_ir(ir: HUSIR) -> HUSReleaseReport:
    canonical = canonical_ir(ir)
    deterministic = canonical == canonical_ir(ir) and plan_hash(ir) == plan_hash(ir)
    validate_ir(ir)
    bounded = all(
        len(w.steps) <= MAX_STEPS and
        all(1 <= s.timeout_seconds <= MAX_TIMEOUT and 0 <= s.retry_limit <= MAX_RETRIES for s in w.steps)
        for w in ir.workflows
    )
    provenance_ready = bool(ir.ir_version and ir.language_version and ir.compiler_version and plan_hash(ir))
    fail_closed = all(s.action.engine and s.action.capability for w in ir.workflows for s in w.steps)
    return HUSReleaseReport(deterministic, bounded, provenance_ready, fail_closed,
                            deterministic and bounded and provenance_ready and fail_closed)
