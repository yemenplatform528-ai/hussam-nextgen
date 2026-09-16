# AI-04 — AI Product Lock

Status: **ENGINEERING LOCKED**

AI-04 closes the governed AI product boundary. It does not claim live provider credentials, external production evidence, or autonomous production execution.

## Closed capabilities

- Provider health evidence and bounded failover evidence.
- First-class evaluation suites/results with explicit thresholds.
- Release gates that remain blocked until required checks pass.
- Security/release snapshot across providers, routes, agents, tools and active memory.
- Control Center change ledger over engineering-defined AI resources.
- Secret/database state rejection at the Control Center boundary.
- Tenant isolation for all AI-04 records and endpoints.
- Marketplace/AI integration remains proposal-oriented; domain services remain authoritative.

## Required AI release checks

The platform supports explicit checks including:

`memory_isolation`, `tool_authorization`, `provider_failover`, `output_validation`, `observability`, `marketplace_integration`, `prompt_injection`, `data_isolation`, `approval_compliance`, and `regression`.

A release gate is `ready` only when the latest result for every required check passes its suite threshold. Missing or failed checks keep the gate blocked.

## Control Center boundary

The Control Center may configure already-engineered AI resources: providers, model routes, agents, tools and evaluation suites. It cannot write secrets, direct database state, tenant authority, ledger truth, payment truth, or new capabilities. All changes are persisted as auditable control changes.

## Provider failover rule

Provider health is evidence, not authority. Model routing remains governed by AI-01 route policy, data-class/privacy requirements and capability requirements. A fallback provider cannot silently receive broader data classes or permissions.

## Final authority

`AI → evaluation/policy → Tool Gateway → Domain Service → Sovereign Core/Persistence`

The model, agent, memory, retrieval result and Control Center are never security boundaries or financial authorities.
