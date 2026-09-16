# AI-03 — Multi-Agent Operations Engineering Lock

Status: **ENGINEERING LOCKED**

AI-03 introduces governed multi-agent orchestration above AI-01 and AI-02. It does not create an autonomous swarm and it does not become a new authority over Marketplace, Finance, Payments, Inventory, Logistics, Identity, or the Sovereign Core.

## Authority model

`Orchestrator → scoped specialist identity → governed context/tools → approval boundary → domain authority`

The orchestrator can select and delegate to enabled specialist agents. It cannot grant a child agent scopes that are not present in its registry definition, escalate data classes, bypass tenant isolation, or execute a domain mutation itself.

## Initial specialist identities

- `customer_commerce_assistant`
- `seller_operations_assistant`
- `marketplace_operations_assistant`
- `finance_assistant` — read-only
- `risk_trust_assistant`

The registry is tenant-scoped. Every delegation records the child identity, explicit scopes, depth, market context, sequence, status, and result.

## Delegation boundaries

- Maximum orchestration depth: 2.
- Maximum selected agents per run: 8, with a default budget of 4.
- Requested agents must already exist and be enabled in the tenant registry.
- Delegation is analysis/proposal oriented; it is not an execution grant.
- Mutation remains behind the AI Tool Gateway, approval policy, and domain service authority.
- No agent receives direct SQL, shell, database, ledger, payment, payout, privilege-elevation, or tenant-reassignment authority.
- A delegation cannot be completed from another tenant.

## Failure isolation

A child agent is independently addressable and its result is persisted against its delegation. A failed or blocked delegation does not grant fallback authority to the orchestrator. The platform records the bounded state instead of silently escalating privileges.

## Control Center compatibility

The future Control Center may enable/disable agents and configure their bounded policy, but it cannot create capabilities outside the engineering-defined contract. New capabilities remain code/engineering work.

## Production boundary

AI-03 is an engineering lock, not a claim of external production evidence. Provider credentials, live model calls, autonomous execution, and external operational evidence remain outside this lock.
