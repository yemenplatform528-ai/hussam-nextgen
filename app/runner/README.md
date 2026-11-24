# Runner V1 prototype — current implementation boundary

This package is a separate prototype. It is not imported by the running application,
not connected to WorkflowEngine, and not deployed.

## Implemented in this branch

- PostgreSQL queue schema under the new `hussam_runner_v1` schema.
- Tenant-scoped repository operations with transaction-local `app.tenant_id`
  and forced row-level security on tenant-owned tables.
- Atomic claim with `FOR UPDATE SKIP LOCKED`, lease expiry and monotonic fencing.
- Idempotent enqueue, attempt history, append-only checkpoints and audit events.
- Expired final-attempt reaper and stale-attempt closure on reclaim.
- Allowlisted handler registry and separate database connection for heartbeats.
- Bounded secret redaction for payload metadata and safe error summaries.
- Transactional schedule occurrence materializer with explicit misfire policies.
- Optional `croniter` adapter using IANA `zoneinfo` and UTC occurrence timestamps.
- Transactional allowlisted Outbox relay from the existing `outbox_events` model into durable tasks.

## Required integration contract

- Supply one PostgreSQL connection per worker operation and a separate connection
  factory for lease heartbeats.
- Set tenant ID only from authenticated server-side context.
- Handler signature is `handler(task, checkpoint, stop_event)`; handlers must check
  `stop_event.is_set()` before each external side effect and use stable idempotency keys.
- Install `hussam-nextgen[runner]` for the included timezone-aware `croniter` adapter,
  or inject a separately tested `next_occurrence(expression, IANA_timezone, after)`.
  DST behavior must still be covered by the release acceptance matrix.
- Keep Redis optional; PostgreSQL remains authoritative.
- Do not put credentials, connection strings, raw exception messages, or secrets in
  task payloads or checkpoints. Redaction is defense in depth, not permission to store secrets.

## Validation

Run the isolated PostgreSQL workflow in GitHub Actions. It applies `schema.sql` only
to an ephemeral PostgreSQL 16 service and runs the queue/RLS/fencing/checkpoint/recovery
tests. Passing CI is required before calling this prototype tested.

## Explicitly not done

- No migration has been applied to any existing database.
- No existing WorkflowEngine, WorkflowTask, Render service, Neon branch, YIB app,
  secret, SSO policy, or billing setting was changed.
- No production deployment, live schedule, or external side-effect handler is enabled.
- Backup/restore drill and provider-neutral packaging remain release gates.
