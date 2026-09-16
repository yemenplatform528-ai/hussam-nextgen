# Production Evidence Register

This is the authoritative release gate for evidence that cannot be proven by unit tests alone.

**Current repository state: 0/10 external gates closed.** This is intentional: no external evidence is fabricated inside the repository.

| Gate | Required evidence | Current state |
|---|---|---|
| Identity/OIDC | production issuer metadata, client registration, secret-manager reference, login E2E | PENDING_EXTERNAL |
| PostgreSQL | real PostgreSQL instance, migration run, backup + restore drill | PENDING_EXTERNAL |
| Payments | certified provider adapters, signed webhook verification, reconciliation evidence | PENDING_EXTERNAL |
| Accounting | external ledger integration + reconciliation evidence | PENDING_EXTERNAL |
| Logistics | verified carrier adapter + delivery evidence | PENDING_EXTERNAL |
| Browser/mobile E2E | real browser/device journeys and artifacts | PENDING_EXTERNAL |
| Security | dependency/image scan, distributed rate-limit evidence, external assessment | PENDING_EXTERNAL |
| Backup/DR/Observability | restore proof, alerts, dashboards, recovery measurements | PENDING_EXTERNAL |
| Operations | on-call ownership, support workflow, rollback and incident drills | PENDING_EXTERNAL |
| Legal/Compliance | approved marketplace policies and applicable compliance review | PENDING_EXTERNAL |

A gate is closed only after its validated evidence envelope and referenced artifact are supplied to the controlled evidence directory. See `docs/PRODUCTION_EVIDENCE_PROTOCOL.md`.
