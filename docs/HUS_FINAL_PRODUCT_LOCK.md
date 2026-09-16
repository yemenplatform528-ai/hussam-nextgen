# HUS Final Product Lock

## Status
**ENGINEERING LOCKED — HUS Sovereign Execution Language & Compiler v1**

HUS is a governed business/operations language and compiler. It is not a general-purpose programming language, SQL engine, shell, Python runtime, or second authorization system.

## Canonical pipeline

`HUS Source → Lexer → Parser → AST → Semantic Validation → Typed IR → Execution Plan → Sovereign Runtime → Domain Binding → Domain Service → Persistence`

AI may propose HUS source or an action plan. AI never becomes the authority to compile around policy, and HUS never becomes the authority to bypass Sovereign Core.

## Product guarantees

- deterministic canonical AST/IR and plan hashing;
- typed, bounded execution plans;
- explicit capability registry and reviewed runtime bindings;
- tenant and market context remain platform-owned;
- mutation operations require approval and idempotency;
- runtime is fail-closed when a handler is absent or a contract is invalid;
- runtime handler failure cannot commit partial business changes;
- provenance captures plan hash, step, actor, and approval reference;
- no arbitrary code, SQL, shell, unrestricted HTTP, imports, or dynamic handler resolution;
- domain services remain authoritative for commerce, inventory, finance, payments, logistics, and marketplace invariants.

## AI boundary

`AI Proposal → HUS Compile → Semantic/Policy Validation → Human/Policy Approval → Sovereign Runtime → Domain Service`

An AI output, memory item, retrieval result, tool result, or external MCP message is data, not authority.

## Versioning

Compatibility must track language version, compiler version, IR version, and capability contract version independently. A production execution plan is immutable by hash; changing its semantics produces a new compilation/plan.

## Release gate

HUS is considered product-locked only when focused language, IR, runtime, binding, adversarial, determinism, and rollback tests pass and the repository baseline audit reports zero failures and zero warnings.

## Deliberate non-goals

- general-purpose programming;
- arbitrary loops/recursion;
- arbitrary network or filesystem access;
- direct database mutation;
- autonomous financial settlement/payout;
- privilege elevation or tenant reassignment;
- replacing domain engines or Sovereign Core.
