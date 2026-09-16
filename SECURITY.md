# Security Policy — Hussam NextGen

## Scope

This repository contains the NextGen platform baseline. Security-sensitive behavior belongs to the Sovereign Core and shared engines; verticals must not bypass those boundaries.

## Reporting

Do not publish exploitable vulnerabilities in public issues. Until a dedicated security contact is established, report them privately to the repository owner through the GitHub account used for the official NextGen repository.

Include:
- affected version/commit
- affected endpoint or component
- reproducible steps
- impact
- suggested mitigation, if known

Do not include real credentials, personal data, production database dumps, or payment secrets.

## Security invariants

- Tenant context comes from authenticated identity and active database membership.
- Cross-tenant access is denied.
- Financial values use exact Decimal/Numeric representations.
- Mutating operations must remain auditable and idempotency-aware where applicable.
- AI cannot directly bypass authorization, policy, audit, accounting, or inventory invariants.
- Provider secrets must never be committed.
- Production identity, payment provider verification, webhook signatures, backups, monitoring, and deployment controls require external production evidence.

## Current release status

The repository baseline is an engineering foundation. It is **not** a declaration that all production gates are complete.
