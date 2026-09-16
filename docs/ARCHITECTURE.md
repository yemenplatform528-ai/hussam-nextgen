# Canonical Architecture

```text
Clients
  -> API Gateway
  -> Identity / Tenant Context
  -> Domain Application Services
  -> Shared Engines
       Finance | Inventory | Commerce | Payments | Logistics | Workflow | Reporting
  -> Sovereign Core
       Policy | Audit | Events | Idempotency | Money | Lifecycle | Registry | Config
  -> Persistence
```

### Dependency boundaries
- Domains may import shared engine contracts and core contracts.
- Shared engines may import Core only.
- Core never imports a vertical domain.
- AI may observe and propose through contracts; it cannot bypass authorization or accounting invariants.

### First production sequence
1. PostgreSQL + migrations + configuration.
2. Identity, membership and tenant isolation.
3. Finance with immutable double-entry lifecycle.
4. Inventory movement/reservation.
5. Commerce and procurement.
6. Payments + reconciliation adapters.
7. Logistics.
8. First verticals.
9. AI orchestration.
10. HUS Compiler.
11. Web/Android hardening and launch gates.

## AI-01 Intelligence Plane

The AI subsystem is a governed intelligence plane above Core and domain contracts. Its control path is:

`AI request -> context contract -> provider/model route -> output validation -> deterministic policy -> typed tool contract -> domain service -> persistence`

AI identities (agents) have explicit scopes, tools, data classes, risk and approval mode. Memory is typed, tenant-scoped, revocable and contextual; live domain records remain authoritative. External retrieval/tool output is untrusted data and cannot become instructions. Model providers are replaceable adapters and are never a security boundary.

The platform also separates the **Engineering Plane** from the **Control Plane**: code creates new capabilities and invariants; the Control Center configures already-designed capabilities through authenticated APIs and domain services. Administrative UI never receives direct SQL authority.
