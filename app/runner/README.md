# Runner V1 prototype — current implementation boundary

This package is a separate prototype. It is not imported by the running application,
not connected to WorkflowEngine, and not deployed.

## Implemented in this branch

- PostgreSQL queue schema under the new `hussam_runner_v1` schema.
- Tenant-scoped repository operations with transaction-local `app.tenant_id`
  and forced row-level security on tenant-owned tables.
- Atomic claim with `FOR UPDATE SKIP LOCKED`, lease expiry and monotonic fencing.
- Idempotent enqueue, attempt history, append-only checkpoints, verified checkpoint restore and audit events.
- Expired final-attempt reaper and stale-attempt closure on reclaim.
- Allowlisted handler registry, separate database connection for heartbeats, and cooperative shutdown that safely defers the active lease.
- Bounded secret redaction for payload metadata and safe error summaries.
- Transactional schedule occurrence materializer with explicit misfire policies, invoked periodically by the process supervisor.
- Optional `croniter` adapter using IANA `zoneinfo` and UTC occurrence timestamps.
- Transactional allowlisted Outbox relay from the existing `outbox_events` model into durable tasks.
- `RunnerService` supervisor that periodically invokes schedule materialization, outbox relay, and expired final-lease reaping before polling the worker.

## Required integration contract

- Supply one PostgreSQL connection per worker operation and a separate connection
  factory for lease heartbeats.
- Set tenant ID only from authenticated server-side context.
- Handler signature is `handler(task, checkpoint, stop_event)`; `task['resume_checkpoint']`
  contains the latest SHA-256-verified checkpoint (or `None`). Handlers must resume from it,
  checkpoint progress, and check `stop_event.is_set()` before each external side effect.
- During graceful shutdown the active handler receives the stop signal; its lease is moved
  to `retry_wait` without recording a task failure. Handlers must use stable idempotency keys
  because a shutdown can occur after an external side effect but before its checkpoint.
- Install `hussam-nextgen[runner]` for the included timezone-aware `croniter` adapter,
  or inject a separately tested `next_occurrence(expression, IANA_timezone, after)`.
  DST behavior must still be covered by the release acceptance matrix.
- Keep Redis optional; PostgreSQL remains authoritative.
- Do not put credentials, connection strings, raw exception messages, or secrets in
  task payloads or checkpoints. Redaction is defense in depth, not permission to store secrets.

## Validation

Use `RunnerService.serve()` for a persistent tenant-scoped process. It runs periodic
schedule materialization, outbox relay (when configured), and final-lease reaping;
`Worker.serve()` remains available when only a queue consumer is required.

Run the isolated PostgreSQL workflow in GitHub Actions. It applies `schema.sql` only
to an ephemeral PostgreSQL 16 service and runs the queue/RLS/fencing/checkpoint/recovery
tests. Passing CI is required before calling this prototype tested.

## Explicitly not done

- No migration has been applied to any existing database.
- No existing WorkflowEngine, WorkflowTask, Render service, Neon branch, YIB app,
  secret, SSO policy, or billing setting was changed.
- No production deployment, live schedule, or external side-effect handler is enabled.
- Backup/restore drill and provider-neutral packaging remain release gates.
