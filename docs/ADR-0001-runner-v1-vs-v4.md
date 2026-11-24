# ADR-0001: Portable Runner V1 versus historical V4

- **Status:** PROPOSED — review required before any database application
- **Date:** 2026-11-24
- **Context:** Historical Runner V4 was tested in archived Neon Staging, but its exact SQL source is not present in the repository and cannot currently be read. Recreating V4 from reports would be unsafe.
- **Decision:** Preserve V4 as historical evidence. Develop a separately named, provider-neutral Runner V1 prototype on an isolated Git branch. Do not call it V4, do not number it as Migration 0043, and do not apply it to any existing database.
- **Scope:** PostgreSQL-backed queue primitives, lease fencing, append-only attempts/checkpoints/audit, allowlisted handlers, redaction, and test scaffolding. Scheduler integration and deployment remain separate acceptance gates.
- **Tenant safety:** Every queue mutation and read is scoped by tenant ID. Production integration must additionally use the application's established tenant authorization/RLS model; this prototype is not a substitute for it.
- **Delivery:** Review the prototype and tests in a draft PR. Run integration tests against a disposable PostgreSQL database. Require an isolated backup/restore drill before production consideration.
- **Rejected:** Reconstructing V4 SQL from prose; waking archived Neon compute; touching Render/YIB; enabling billing; weakening authentication or network controls.
- **Consequences:** The new code is a candidate implementation, not an approved schema migration or deployed worker. Existing WorkflowEngine and WorkflowTask remain unchanged.
