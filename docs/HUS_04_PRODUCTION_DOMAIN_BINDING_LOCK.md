# HUS-04 — Production Execution & Domain Binding Lock

## Purpose
Bind HUS execution to explicit, existing Hussam domain/application contracts without turning HUS into a second business engine.

## Binding model
HUS Runtime resolves only a static allow-list of reviewed handlers:

`Execution Plan -> Sovereign Runtime -> Binding Registry -> Domain Service/Application Contract -> Persistence`

No dynamic import, SQL, shell, HTTP, filesystem access, or model-generated handler names are permitted.

## Production bindings
- `retail.catalog.read` -> governed retail overview read contract
- `inventory.inventory.read` -> governed inventory stock read contract
- `commerce.sales.read` -> governed sales summary read contract
- `marketplace.marketplace.read` -> governed marketplace overview read contract
- `finance.finance.read` -> tenant-scoped finance journal summary
- `payments.payments.read` -> tenant-scoped payment intent summary
- `commerce.sales.create` -> `CommerceProductionService.create_order` with strict argument shape and existing domain invariants

Mutation bindings are never treated as executed merely because a capability is registered. A runtime handler must exist, approval must be present, idempotency must be present, and domain invariants remain authoritative.

## Approval hardening
HUS-04 adds an optional production approval verifier to the runtime. Production deployments should configure it so `approval_ref` is verified against an authoritative approval record before mutation execution.

## Isolation
Every binding receives the tenant from `RuntimeContext`; handlers do not accept a caller-supplied tenant override. Domain services remain authoritative for tenant, inventory, accounting, payment, and marketplace invariants.

## Non-goals
HUS is not a replacement for Commerce, Inventory, Finance, Payments, Logistics, or Marketplace. It orchestrates through contracts; it does not own their business rules.

## Lock decision
HUS-04 is engineering-locked when focused HUS/AI tests, compileall, and baseline audit pass. Full-suite results remain subject to the repository's existing long-running production-evidence tests and must not be represented as a full pass unless completed.
