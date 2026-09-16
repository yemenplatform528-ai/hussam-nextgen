# Production Runbook Skeleton

## Deployment order
1. Provision secret manager and inject production `DATABASE_URL`, `JWT_SECRET`, and OIDC values.
2. Provision PostgreSQL and verify network/TLS policy.
3. Run `alembic upgrade head` as a separate migration job.
4. Start API containers with `ENVIRONMENT=production`.
5. Verify `/health` and `/ready`.
6. Execute browser/mobile smoke journeys.
7. Verify payment webhook signature path and reconciliation queue.
8. Verify observability dashboards and alerts.
9. Record deployment commit/artifact digest.

## Rollback
- Stop new application rollout.
- Restore previous immutable application artifact.
- Never downgrade the database automatically.
- If a migration is incompatible, follow the migration-specific recovery procedure and restore from the verified backup only after incident approval.

## Incident minimums
- Preserve request IDs, audit events and outbox records.
- Capture provider references before replaying payment events.
- Use idempotency keys for all replayable commands.
- Record operator, time, scope and outcome for manual remediation.

## G09 operational control
- Immutable application artifacts are identified by version and SHA-256.
- Application rollback is allowed only when the target artifact is compatible with the current database revision.
- Database downgrade is never an automatic rollback action.
- Incident handling follows `DETECTED → TRIAGED → CONTAINED → RECOVERED → VALIDATED → CLOSED`.
- Every manual remediation records actor, action, outcome and timestamp.
- RTO/RPO targets are service objectives and must be validated with measured external drills.
