# YIB Operational Truth — Single Active Line

Recorded: 2026-10-05
Operational rule: ONE ACTIVE LINE
Live YIB baseline: Tiniest Cloud v30
Truth authority: live runtime evidence + readback

## Current verified state

- system:truth-contract: schema 1.1 — present/readable.
- system:capability-registry-v2: schema 2.0 — present/readable.
- system:runtime-capability: schema 2.1 — present/readable.
- system:execution-state-machine: schema 1.0 — present/readable.
- system:recovery-contract: schema 1.0 — present/readable.
- system:substitution-contract: schema 1.0 — present/readable.
- system:anti-drift-contract: schema 1.0 — present/readable.
- system:portable-recovery-manifest: schema 1.0 — present/readable.
- evidence:runtime-capability-test:1791158770635: verified local runtime execution and explicit external BLOCKED results.
- evidence:reconciliation:1791158770104: verified reconciliation of legacy declarations against live runtime evidence.
- recovery:YIB-KERNEL-001:0001: READY / checkpoint-preserved.

## Runtime truth

| Capability | Truth |
|---|---|
| tiny.ai | EXECUTABLE |
| tiny.db | EXECUTABLE |
| tiny.fetch | BOUNDED |
| github-api | BLOCKED — no connection key |
| gitlab-api | BLOCKED — no connection key |
| notion-api | BLOCKED — no connection key |
| dropbox-api | BLOCKED — no connection key |
| render-api | BLOCKED — no connection key |

AVAILABLE is not equivalent to EXECUTABLE. No capability is promoted without fresh evidence and readback.

## Recovery truth

Recovery contract: PRESERVE → CHECKPOINT → SUBSTITUTE → VERIFY → RESUME → RECORD

Automatic destructive restore is disabled.

## Human boundary

High-risk writes and irreversible, financial, identity, legal, secret-bearing, or ownership-sensitive actions remain fail-closed and require human authority.

## Known drift

The live v30 source currently contains a UI label that says YIB v29. This is a source/UI truth-drift defect, not a reason to create a parallel operational release.

A corrective deployment was not claimed because the deployment/preview path was blocked by a security gate. The live operational baseline remains v30.

## Single-line operating rule

Do not create parallel operational releases. Repair the current line, verify it, record evidence, checkpoint, and continue. Immutable platform versions are retained only as recovery history.

## Completion rule

YIB is not certified merely because the UI loads or a deployment succeeds. Every capability must end as VERIFIED, or BLOCKED with a real documented constraint, or WAITING_HUMAN where authority cannot safely be automated.

Never convert an unknown or declaration into a success claim.
