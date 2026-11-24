# Hussam Portable Task Runner — Recovery-First Design

**Status:** DESIGN HISTORY + PARTIALLY IMPLEMENTED V1 PROTOTYPE / NOT INTEGRATED / NOT DEPLOYED  
**Evidence date:** 2026-11-24  
**Base:** `main` at `d83958a03d3b8194859cbef250c218cb09b4df2f`  
**Working branch:** `design/portable-task-runner-2026-11-23`

> **Implementation update (2026-11-24):** The design below remains the decision record and evidence snapshot that guided implementation. A separate, non-integrated Runner V1 prototype now exists under `app/runner/` on [PR #193](https://github.com/yemenplatform528-ai/hussam-nextgen/pull/193). Its current acceptance status and exact implemented boundary are maintained in [`app/runner/README.md`](../blob/prototype/portable-runner-v1-2026-11-24/app/runner/README.md). The prototype is not merged, connected to WorkflowEngine, migrated into an existing database, or deployed.
>
## 1. Decision

Keep the existing `WorkflowEngine` as the deterministic business-workflow state machine. Add a separate portable execution plane for durable tasks, leases, checkpoints, scheduling, retries, and worker recovery. The workflow layer emits commands/events; the runner owns execution lifecycle. Do not replace `WorkflowEngine` or overload `WorkflowTask` with queue semantics.

PostgreSQL is the durable source of truth. Redis may be used later as a wake-up/notification optimization only; it must never be the only copy of queued work. The worker must remain runnable against ordinary PostgreSQL without Render-specific APIs.

## 2. Evidence baseline (read-only checks, 2026-11-23)

- GitHub repository: `yemenplatform528-ai/hussam-nextgen`, public, default branch `main`; connected GitHub identity has repository push permission.
- Latest `main` commit observed: `d83958a03d3b8194859cbef250c218cb09b4df2f`.
- `app/engines/workflow.py` contains `WorkflowEngine` for workflow definitions, instances, transitions, tasks, and Outbox event emission.
- `app/core/models/workflow.py` defines `WorkflowTask` with status, attempts, last_error, timestamps, and tenant/instance/task-key uniqueness. It has no lease owner/expiry/fencing token, checkpoint, or worker heartbeat fields.
- `app/core/governance/outbox_repository.py` appends events, lists unpublished events, and marks them published. It does not implement an atomic leased relay with retry/backoff.
- `pyproject.toml` already declares `psycopg[binary]`, SQLAlchemy, Alembic, and Redis. Do not add a second database driver.
- GitHub code/branch searches on 2026-11-23 found no `hussam_runner`, `claim_next_task`, or Runner branch.
- Historical Staging evidence records Runner schema V4 and six targeted lease/recovery checks passing on 2026-11-13. The original V4 SQL is not present in current `main`, and the Neon Staging branch is now archived. Treat V4 as historically tested, not currently runnable or source-recoverable.
- Neon Staging, Production, Ops Ledger, YIB runtime, and YIB checkpoint branches were read as archived on 2026-11-23. Staging has one manual snapshot from 2026-09-26; Production and Ops Ledger have none. Automatic snapshot schedules on Staging, Production, and Ops Ledger are empty.
- Render read-only inventory in the owner-recorded workspace returned eight services, no Postgres instances, no Key Value instances, and zero Render Workflows. No dedicated Hussam worker/runner was observed.
- YIB Tiniest app: live v74; v75 and v76 are unpublished drafts. Its app data is private. The latest truth record says the protected Render application export still needs the owner-held connection key and has not run. No `backup:` records exist; two checkpoints exist. This application export is chat/state data only, not a full PostgreSQL dump.
- The YIB app's evidence record says its three-job plan limit was already reached, so an additional on-demand job was not created. Do not upgrade or enable billing to work around this.

## 3. Non-negotiable invariants

1. Tenant isolation is enforced in every claim, update, checkpoint, audit read, and idempotency lookup.
2. A task claim is atomic and uses `FOR UPDATE SKIP LOCKED` (or an equivalent proven atomic primitive).
3. Every lease has a monotonically increasing fencing generation. Completion, failure, checkpoint, and heartbeat writes must match task ID, worker ID, generation, and unexpired lease.
4. A stale worker cannot mutate a task after lease expiry or after a newer generation is issued.
5. Delivery is at-least-once. Side effects require stable idempotency keys and handler-level deduplication; never promise exactly-once execution.
6. Task attempts and audit events are append-only evidence. State transitions are explicit and constrained.
7. Checkpoints are versioned, bounded, tenant-scoped, and contain resumable state only; no credentials, access tokens, connection strings, or raw secrets.
8. Scheduler materializes due work transactionally with a unique occurrence key. DST and missed-run behavior are explicit and tested.
9. Logs are structured and allowlisted. Persist error codes and safe summaries, not raw exception strings, request headers, environment values, or arbitrary payloads.
10. No production migration, deployment, compute wake-up, resource creation, billing change, or security relaxation is part of this design branch.

## 4. Target persistence contracts (conceptual; not SQL yet)

### Task
- Identity: task ID, tenant ID, task type, schema/version, idempotency key.
- Input: validated, size-bounded payload with a documented allowlist.
- Scheduling: priority, `run_after`, deadline/expiry, max attempts.
- State: pending, running, retry_wait, succeeded, failed, dead_letter, cancelled.
- Lease: worker ID, lease expiry, fencing generation.
- Timestamps: created, updated, started, completed.
- Safe failure: error code and redacted summary only.

### Attempt
- Append-only attempt number, task ID, worker ID, fencing generation, start/end, outcome, safe error code, and duration.
- No raw exception or credential-bearing context.

### Checkpoint
- Task ID, sequence, handler version, schema version, safe state payload, checksum, created time, and fencing generation.
- New checkpoint records supersede older ones; do not overwrite the only recovery point.

### Schedule
- Tenant ID, handler/task type, cron expression, IANA timezone, enabled flag, next/last occurrence, misfire policy, and occurrence idempotency key.
- Scheduler lease/fencing prevents two schedulers from materializing the same occurrence.

### Worker heartbeat
- Worker ID, process instance ID, build/version, capabilities, last-seen time, and bounded health metadata.
- Heartbeats contain no host secrets or full environment.

### Outbox delivery
- Event ID, tenant, destination/handler, attempt count, next retry, lease/fencing, delivered timestamp, and safe error code.
- Claim and acknowledgement are atomic; retries use bounded exponential backoff with jitter.

## 5. Worker contract

- Python 3.11+ using the existing `psycopg` dependency.
- Explicit handler registry; never import a handler named by untrusted payload text.
- Bounded concurrency, graceful shutdown, lease renewal, heartbeat, cancellation checks, and bounded execution time.
- Claim only tasks whose `run_after <= now()`, whose lease is absent/expired, and whose state is eligible.
- Renew lease well before expiry; stop side effects if renewal fails.
- Commit checkpoint before acknowledging progress.
- On process termination, allow lease expiry and safe reclaim; do not manually rewrite task state from an external shell.
- Use database transactions for queue state, but keep long external work outside transactions.
- PostgreSQL remains authoritative if Redis or a notification channel is unavailable.

## 6. Secret-safe logging

- Log only: timestamp, task ID, tenant-safe correlation ID, handler name/version, attempt, worker ID, duration, outcome, safe error code.
- Redact bearer tokens, JWTs, API keys, passwords, connection strings, cookies, authorization headers, private keys, and common secret assignments before any log/evidence write.
- Do not log full task payloads, checkpoint payloads, HTTP request/response bodies, or environment variables.
- Add tests that inject fake secrets in nested JSON, exception messages, URLs, headers, and multiline stack traces and assert that no raw value appears in logs, audit, or checkpoints.
- Treat a redaction failure as fail-closed: suppress the unsafe message and record a fixed error code.

## 7. Recovery and acceptance test matrix

| Scenario | Required assertion |
|---|---|
| Two workers claim concurrently | One current lease generation per task |
| Worker killed after claim | Task is reclaimed only after lease expiry |
| Old worker resumes | Fencing rejects complete/fail/checkpoint/heartbeat writes |
| Lease renewal fails | Worker stops protected side effects |
| Crash after checkpoint | New worker resumes from latest valid checkpoint |
| Duplicate enqueue | Tenant-scoped idempotency returns the same logical task |
| Duplicate external event | Handler/outbox dedupe prevents duplicate side effects |
| Retryable failure | Backoff and attempt count are durable |
| Attempts exhausted | Task enters dead-letter with terminal attempt closed |
| Scheduler concurrency | One row per schedule occurrence |
| DST spring/fall transition | Defined timezone and misfire policy is deterministic |
| Outbox relay crash | Event is retried without losing delivery evidence |
| Secret injection | No canary secret appears in logs, audit, task errors, or checkpoints |
| Backup/restore | Restored isolated database passes schema, row-count, queue, and resume checks |

A test is PASS only when it executes against an isolated PostgreSQL database and asserts the persisted result. Static inspection is not a recovery test.

## 8. Recovery-first migration rule

The historical V4 SQL is missing from current GitHub and the original Staging branch is archived. Therefore:

- Do not fabricate or label a new schema as recovered V4.
- Do not create Migration 0043 until the exact V4 schema/functions are recovered and compared.
- First obtain a provider-supported, non-destructive export or restore of the archived Staging timeline, or another byte-exact trusted source.
- If V4 cannot be recovered, open a separate architecture decision for a new runner schema/version. Keep it distinct from V4 and require review before migration numbering or application.
- Any schema work starts on a disposable isolated database, followed by migration round-trip tests and recovery drills.
- Production remains untouched until backup/restore, compatibility, security, and rollback evidence are complete.

## 9. Delivery phases

1. **Source recovery:** recover exact V4 SQL and compare it with this contract.
2. **Schema validation:** isolated migration, constraints, indexes, RLS/tenant tests, and downgrade/forward compatibility review.
3. **Worker implementation:** claim/lease/fencing, handler registry, heartbeat, graceful shutdown, checkpoint resume.
4. **Scheduler and Outbox:** occurrence materialization, leased relay, retries, dead-letter handling.
5. **Security:** redaction, payload validation, least-privilege DB role, audit allowlist.
6. **Recovery drill:** kill/restart workers, restore isolated backup, resume tasks, verify no stale-worker writes.
7. **Portable packaging:** container/CLI entry point, environment-variable names documented without values, PostgreSQL URL supplied only at runtime, provider-neutral deployment instructions.
8. **Release gate:** reviewed PR, CI, artifact hash, isolated restore evidence, and explicit owner approval before production.

## 10. Current blockers and safest next actions

- **Archived Neon source:** exact V4 SQL cannot be read without provider-supported branch recovery or a trusted export. Do not start compute or restore/finalize branches automatically.
- **Render YIB database:** the previously recorded database is no longer in the current Render Postgres inventory. A 404/no-inventory result does not prove deletion. Request provider/owner recovery confirmation for the exact resource ID; no billing workaround.
- **No hosted queue/worker:** Render inventory currently has no Postgres, Key Value, or Workflow resource. Do not create paid or replacement resources under this design.
- **YIB application export:** v76 remains draft and export requires the owner-held private connection key. It is only an application-level state/chat export, not a full PostgreSQL backup. Do not publish or execute it without the owner-controlled key and a reviewed test plan.

**Current conclusion:** the existing workflow orchestration is implemented; a portable durable runner is not yet implemented. Historical Runner V4 tests are evidence of prior behavior, not a current deployable artifact. This document is a design and recovery plan only.
