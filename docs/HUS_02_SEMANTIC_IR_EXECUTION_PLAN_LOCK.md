# HUS-02 — Semantic IR & Execution Plan Engineering Lock

## Purpose
HUS-02 converts the validated HUS-01 AST into a deterministic, typed, bounded Intermediate Representation (IR) and declarative execution plan.

## Locked invariants
- IR is data, never executable code.
- Every action resolves through the existing allow-listed capability registry.
- Workflow dependencies are explicit and bounded; the current lowering is deterministic sequence semantics.
- Mutations require explicit approval and idempotency.
- Read actions do not require approval or idempotency by default.
- Timeouts and retries are bounded constants at this stage.
- No loops, recursion, dynamic imports, SQL, shell, filesystem escape, arbitrary HTTP, or direct database mutation.
- Domain services remain the only business execution authority.
- AI may propose HUS/IR but cannot grant authority.

## IR identity
Each release carries:
- language version
- compiler version
- IR version
- capability references
- workflow/step identifiers
- dependency edges
- risk class
- approval requirement
- timeout/retry policy
- idempotency requirement
- compensation slot

`execution_plan_hash` is the canonical SHA-256 of the IR. Whitespace and source formatting do not change it.

## Runtime boundary
HUS-02 deliberately stops before arbitrary runtime dispatch. A future runtime must re-check tenant, market, actor, authorization, approval, policy snapshot, idempotency, and capability contract at execution time.

## Release evidence
- Focused HUS/AI regression suite must pass.
- Python compileall must pass.
- Baseline audit must report zero failures/warnings.
- Any full-suite timeout is recorded as an evidence limitation, not a false pass.
