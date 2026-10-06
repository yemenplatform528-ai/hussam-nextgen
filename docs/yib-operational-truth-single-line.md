# YIB Operational Truth — Single Active Line

Recorded: 2026-10-06
Operational rule: ONE ACTIVE LINE
Live YIB baseline: Tiniest Cloud v33 (ACTIVE)
Access: private / restricted
Truth authority: live runtime evidence + readback

## Current verified state

- Main repository head: 8b6b85ba734fc7c198083b8113934e8eebe65c10.
- system:capability-registry-v2: schema 2.0 — present/readable.
- system:runtime-capability: schema 2.1 — present/readable.
- system:execution-state-machine: schema 1.0 — present/readable.
- system:recovery-contract: schema 1.0 — present/readable.
- system:substitution-contract: schema 1.0 — present/readable.
- system:anti-drift-contract: schema 1.0 — present/readable.
- system:portable-recovery-manifest: schema 1.0 — present/readable.
- latest recorded runtime-capability test: 2026-10-05T01:52:40.518Z.
- latest runtime evidence verifies tiny.ai=EXECUTABLE, tiny.db=EXECUTABLE, tiny.fetch=BOUNDED and the five external connections as BLOCKED.
- current persisted system:truth-contract readback is schema 1.0 from the pre-v33 runtime self-test.
- v33 source contains the corrected schema 1.1 truth-contract write path, but post-v33 execution/readback of that write is NOT independently verified.
- recovery checkpoint is preserved; recovery state is resumable/route-ready.
- high-risk approval remains WAITING; external execution remains disabled.

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

Provider substitution is required by the continuity contract. Real outage/failover execution is not yet independently verified.

## Human boundary

High-risk writes and irreversible, financial, identity, legal, secret-bearing, or ownership-sensitive actions remain fail-closed and require human authority.

## External certification gates

G01–G10 remain open because their closure requires real external evidence, not code inspection alone. Browser E2E is not independently verified, current main CI status is NOT ASSERTED, Basic Memory connector read access is currently blocked, and legal/compliance decisions remain human-controlled.

## Recovery branch

continuity/recovery-2026-10-01 remains a preserved recovery/historical branch. It is diverged from main and is not an active development line. It is not merged or deleted automatically.

## Single-line operating rule

Do not create parallel operational releases. Repair the current line, verify it, record evidence, checkpoint, and continue. Immutable platform versions are retained only as recovery history.

## Completion rule

YIB is not certified merely because the UI loads or a deployment succeeds. Every capability must end as VERIFIED, or BLOCKED with a real documented constraint, or WAITING_HUMAN where authority cannot safely be automated.

Never convert an unknown or declaration into a success claim.
