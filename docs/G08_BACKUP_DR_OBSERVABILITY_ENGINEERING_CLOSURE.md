# G08 — Backup / DR / Observability Engineering Closure

**Engineering status:** `ENGINEERING_READY`

**Production certification status:** `PENDING_EXTERNAL`

## Scope

G08 covers controlled PostgreSQL backup/restore, recovery verification, runtime health/readiness, metrics, structured logs, alert rules, and an external observability probe.

## Engineering controls

- `scripts/postgres_backup_restore_drill.sh` requires PostgreSQL, creates a custom-format backup, verifies the archive, restores only to an explicitly distinct target, checks connectivity, and optionally verifies the expected Alembic revision.
- Backup/restore evidence is never fabricated by unit tests.
- `/health` is a lightweight process probe.
- `/ready?deep=true` performs a real database `SELECT 1` probe in the target environment.
- `/metrics` exposes Prometheus-compatible counters for requests, failures, duration, process start time, and last deep-readiness state.
- Structured JSON logs carry request IDs and deliberately exclude credentials and request bodies.
- `config/observability/prometheus-alerts.yml` defines availability, readiness, 5xx-rate, and no-traffic alerts.
- `scripts/production_observability_probe.sh` captures health/readiness/metrics results without collecting secrets.

## External evidence still required

1. Real PostgreSQL backup creation and restore into an isolated recovery target.
2. Restore timing and measured RPO/RTO against the approved objectives.
3. Real monitoring/dashboard deployment scraping `/metrics`.
4. Real alert delivery to the operational notification channel.
5. Failure/recovery drill with reviewer decision and artifact hash.

G08 is not production-closed until the evidence envelope is validated under the production evidence protocol.
