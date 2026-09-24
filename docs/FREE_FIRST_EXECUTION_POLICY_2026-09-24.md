# Hussam NextGen — Free-First Execution Policy
## $0 operating constraint — 2026-09-24

### Decision
The current project constraint is **$0 out-of-pocket**. Engineering must continue without requiring a paid subscription, paid trial, credit purchase, paid domain, paid compute, paid database, or paid AI/API quota.

This is an execution constraint, not a redesign of the architecture.

### Rules
1. Sovereign Core and Shared Engines must not require a paid provider to boot, test, migrate, or execute their core invariants.
2. External providers are adapters. A provider may be unavailable without corrupting the platform's internal state.
3. AI is optional at runtime. Core workflows must remain executable with a disabled/local/fallback AI mode where the domain contract permits it.
4. Email, SMS, WhatsApp, maps, payment rails, storage and other external services are integration capabilities, not hidden core dependencies.
5. A free hosting tier may be used for development, preview or staging only when its durability and availability limits are explicitly accepted.
6. No ephemeral free database is treated as the authoritative production datastore.
7. No local filesystem on an ephemeral host is treated as durable business storage.
8. No release gate may be marked closed merely because a provider configuration exists; external certification requires artifact-backed evidence.
9. If a required external capability has no safe $0 path, classify it as **EXTERNAL_BLOCKED** and keep the internal architecture provider-neutral rather than inventing a false completion.
10. Future paid infrastructure must be an operational substitution behind an existing adapter/contract, not a Core rewrite.

### Current $0 engineering stack
- Source control: public GitHub repository.
- CI: GitHub-hosted standard runners for the public repository.
- Application tests: Python, pytest, Playwright/Chromium and local PostgreSQL in CI.
- Database development/integration: local PostgreSQL/SQLite in controlled test environments.
- Preview/staging: free-tier hosting only where its documented limitations are acceptable.
- Production data: not declared durable until a persistent, backed-up PostgreSQL capability is available.
- Domain: provider subdomain is acceptable during the $0 phase.
- AI: contract/adapter first; no paid AI quota is required by Core.
- Payments/notifications/logistics: provider adapters and test doubles until real external credentials/evidence exist.

### Release meaning
"$0" does not mean "production-ready for free." It means the engineering path must remain executable at zero cost while preserving a clean migration path to durable production infrastructure.

The final release gate remains fail-closed:
- exact source commit;
- trusted CI evidence bound to that commit and source manifest;
- complete release manifest;
- all external G01–G10 evidence envelopes;
- rollback/migration evidence;
- final immutable release artifact.

### Explicit non-goals
This policy does not:
- declare any external provider certified;
- close G01–G10 without evidence;
- convert a free staging database into production authority;
- weaken authentication, authorization, tenant isolation, accounting, payment, idempotency, audit or security controls;
- authorize arbitrary runtime shell, SQL or network execution through the Developer Platform.

### Exit from the $0 constraint
When funding becomes available, paid infrastructure may be introduced only by replacing adapters/infrastructure bindings while preserving the application contracts and data/domain invariants.

