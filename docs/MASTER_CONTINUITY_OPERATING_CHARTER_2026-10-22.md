# الحسام اليمني ⚔️🇾🇪 — Master Continuity & Execution Charter

**Status:** Active operating directive  
**Created:** 2026-10-22  
**Purpose:** Preserve the user's intent across sessions, prevent project drift, and govern evidence-based execution. This document is a durable project checkpoint; it does not by itself alter ChatGPT account-wide memory or guarantee that every new chat automatically loads it.

## 1. Mission and user delegation

The user's overarching mission is to build useful, trustworthy, Arabic-first technology capabilities for Yemenis. “Yemen is the purpose; AI is a capability layer.” The target is not merely a chat UI, a list of links, or a demo. The work should progress through discovery, research, design, implementation, tests, verification, deployment, operations, recovery, security, documentation, and continuous improvement.

The user has delegated planning and continuation: when they say **«أكمل»**, resume from the latest evidence-backed checkpoint, make the highest-value safe progress available, and avoid asking them to re-explain established context. Do not scatter effort across unrelated tracks or restart completed investigations without a specific reason.

## 2. Operating rules

1. **Continuity over restart:** load this charter and the latest evidence/checkpoint before choosing the next action.
2. **Evidence over confidence:** label material claims `VERIFIED`, `OBSERVED`, `REPORTED`, `INFERRED`, `BLOCKED`, or `UNKNOWN`. A written plan, HTTP 200, green CI, or successful deployment alone does not prove full product readiness.
3. **No fabricated execution:** claim an external action only after the relevant system returns evidence and a read-back confirms the result.
4. **One portfolio, distinct products:** coordinate the overall mission, but keep product source code, release lifecycle, runtime, data, secrets, ownership boundaries, and rollback paths independent where appropriate.
5. **No unnecessary repetition:** reuse established findings and repeat checks only when evidence is stale, conflicting, or the action requires fresh confirmation.
6. **Arabic-first, resilient, practical:** favor clear Arabic UX, weak-network tolerance, low operating burden, and no payment setup where avoidable; do not falsely constrain all options to free tiers if that would undermine the mission.
7. **No secrets in records or chat:** record secret names and configuration status only, never values, tokens, passwords, or private keys.
8. **Protect user assets:** do not delete data, rewrite protected history, change ownership/access, rotate credentials, incur costs, upgrade subscriptions, or perform irreversible/high-risk production actions without the required explicit approval.
9. **Safe autonomous work:** proceed independently with read-only audits, documentation, local changes, tests, and reversible low-risk work when authorized. Before deployment or other consequential side effects, confirm authorization scope, tests, backup, rollback, and exact target.
10. **Completion requires proof:** never declare 100% complete until the applicable acceptance gates have current evidence. If blocked, name the precise blocker and the smallest next action.

## 3. Product portfolio — keep these tracks distinct

- **Hussam AI standalone assistant:** Arabic-first independent chat experience; inference bridge; live provider verified by a real response; authentication/session protection; privacy-defined history; provider failure handling and rate limits.
- **YIB / WORLD:** independent operational/continuity bridge, authority and trust policy, capability map, evidence ledger, checkpoints, owner approval boundaries, and provider-neutral inference. A healthy API without an enabled provider is not live AI.
- **Hussam NextGen / Yemenization commerce platform:** governed marketplace and business platform, tenant isolation, money/accounting, inventory/orders, payments, logistics, documents, notifications, AI/HUS integration, migrations and production gates.
- **Yemen connectivity / satellite information portal:** clearly distinguish an information and guidance portal from a real operated network or connectivity service. Never claim ownership or service availability without external evidence.
- **Memory Core / Command Center / Yemen Launch / Analyst-related work:** determine each product's actual purpose, authority, data ownership, runtime, dependencies and overlap through evidence; do not assume that similarly named systems share memory, inference, or control.

## 4. Priority order

### P0 — Protect data and recovery
- Map every production database to the exact service/repository/branch and environment without exposing connection strings.
- Verify backup/export capability, create a protected independent backup where authorized, compute/check a checksum, and restore to an isolated target.
- Validate schema, migrations, data integrity, restore time (RTO) and recovery-point objective (RPO).
- Track expiry/deletion windows, especially the previously observed Render PostgreSQL resource with recorded expiry **2026-11-07**; re-check current provider state and policy. Do not pay, upgrade, or change billing without approval.
- Never perform destructive migrations or remove old data before recovery is demonstrated.

### P1 — Secure and verify Hussam AI
- Production portal previously showed no login/session UI; auth PR #118 (`security/hussam-ai-session-auth-2026-10-17`, head `b2ac2a297680683e870ed00d581b9c1ebf87768b`) had CI evidence but was not verified deployed. Re-check live state before acting.
- The inference bridge previously returned a verified Gemini response (`gemini-3.8-flash`) through `POST /api/chat`; avoid unnecessary generation calls because they may consume quota.
- Reconcile portal and backend deployment versions, implement/verify session login/logout, secure cookie/session settings, origin restrictions, rate limits, failure semantics, and rollback.
- Required secret names were previously `HUSSAM_ACCESS_PASSWORD` and `HUSSAM_SESSION_SECRET`; set them only in the authorized host's secret settings, never in chat or logs. Confirm exact allowed origin against the live deployment before configuration.

### P2 — Restore YIB live inference under owner control
- Last observed Render YIB health was `PASS` but `provider: NONE`, `modelConfigured:false`, `liveModelVerified:false`, `auth: REQUIRED`, `POSTGRES_DURABLE`, `paidOpenAIAllowed:false`.
- PR #119 (`feat/yib-provider-neutral-runtime` / `docs/yib-current-free-tier-model-2026-10-19`, head `ca3fea4cd0ecbfca8a221999f9f3520999080616`) had four passing CI jobs but was gated on owner-authorized provider configuration.
- Re-check current branch/PR/deployment/provider state; configure only a provider the owner has authorized and can lawfully use; perform one bounded, non-sensitive generation test, capture response/status/model evidence, and preserve fail-closed behavior if unavailable.

### P3 — Reconcile source of truth and independent products
- Build a service map: product → canonical repository → branch/commit → build/test status → deployment/service → domain → database → provider → auth → owner → backup/restore → monitoring → cost/expiry.
- Identify stale branches, duplicated product roots, disconnected deployments, drifted environment variables, and hidden shared dependencies.
- Split projects incrementally, beginning with the comparatively scoped `yemen-satellite-zero`, then Hussam AI, then YIB/WORLD/Memory Core, and the commerce platform after mapping and backup. Do not delete or merge branches merely because names look obsolete.
- Treat FastAPICloud, Render, Neon, Tiniest Cloud, and Vercel as distinct providers; a healthy URL or deployment does not prove which database, provider, or source revision it uses.

### P4 — Close commerce and production gates

Track the repository's G01–G10 production gates with attributable evidence: identity/OIDC; PostgreSQL migrations and restore; payment provider certification, signed webhooks and reconciliation; accounting; logistics/carrier operations; browser/mobile E2E; security and distributed rate limits; backup/DR/observability; operations/rollback/incident runbooks; legal/compliance/marketplace review. Do not call production-ready while applicable external gates remain open.

### P5 — Operate and improve continuously

Maintain monitoring, quota/cost/expiry alerts, backups and restore drills, regression/security checks, incident records, release provenance, dependency reviews, rollback instructions, and periodic cleanup based on evidence. Improve one high-value slice at a time while retaining the full portfolio view.

## 5. Required evidence ledger

For each product/service, maintain at least:

- last checked timestamp (UTC), checker/method, environment and exact source SHA/deployment ID;
- observed endpoint/status and sanitized response summary;
- tests and CI run IDs for the exact commit;
- database identity/branch mapping (no credentials), migration state, backup ID/checksum, restore test result;
- provider/model configured and whether a real generation was observed;
- authentication and authorization status;
- unresolved blockers, risks, cost/expiry, rollback and next action;
- evidence status labels listed above.

Never mix evidence from different commits, deployments, environments, or products without explicitly stating the mismatch.

## 6. Completion gates

A product can be marked complete only when applicable gates are evidenced for the exact release:

1. Functionality and acceptance tests pass.
2. Security, identity, authorization, and privacy are verified.
3. Data schema/migrations and integrity are verified.
4. Independent backup and successful restore are evidenced.
5. Runtime/provider behavior is verified (or clearly marked intentionally unavailable).
6. Monitoring, incidents, operations, rollback, and recovery runbooks exist and are tested.
7. Costs, quotas, expirations, dependencies, and owner controls are known.
8. Deployment/release provenance and CI are tied to the exact source SHA.
9. Applicable external/legal/commercial gates are closed.
10. The next maintenance/review point and current checkpoint are recorded.

Use percentages only when they are computed from explicit, weighted, evidenced acceptance criteria; never invent a “100%” score.

## 7. Resume protocol for any new chat

When continuing this project in a new chat:

1. Retrieve this file from the canonical repository, plus the latest execution checkpoint and evidence ledger.
2. Re-check only time-sensitive/high-risk facts that may have changed since the last checkpoint.
3. State the current truth briefly, including what is verified and what remains blocked.
4. Select the highest-priority safe action, execute it with available authorized tools, test/read back the result, and record the evidence.
5. Update this charter/checkpoint as the work evolves; never claim the new chat has automatically loaded this file unless it actually has.

If repository or tools are unavailable in a new chat, use this compact continuation instruction:

> Continue the Hussam Yemen project under `docs/MASTER_CONTINUITY_OPERATING_CHARTER_2026-10-22.md` in `yemenplatform528-ai/hussam-nextgen`. Resume from current evidence, do not restart, do not claim unverified actions, prioritize data backup/restore, Hussam AI authentication, YIB live inference, then product independence and remaining production gates. Execute the highest-value safe next step and record evidence.

## 8. Initial evidence-backed checkpoint (2026-10-22)

These are inherited findings and must be re-checked before consequential action; they are not a claim that the current live state is unchanged:

- Local Codespace: `/workspaces/hussam-nextgen`; branch `main`; commit `be8925f` (full SHA previously observed as `be8925f7f619d22a3ab1b01804185dc0adafe962`); working tree was clean and synced with `origin/main` at the time of check.
- Python test collection in the Codespace previously failed because required packages (`SQLAlchemy`, `FastAPI`) were absent; this is an environment/dependency failure, not proof all application tests fail.
- Hussam AI auth PR #118 had CI evidence but production deployment/auth UI was not verified; prior production login route returned 404.
- Hussam AI inference bridge previously returned a successful Gemini response; avoid quota-consuming repeat calls unless necessary.
- YIB Render was healthy but had no enabled provider/live model at last check; protected endpoints correctly required auth.
- Render PostgreSQL `yib_world_independent_memory` was previously observed available on the free tier with a recorded expiry date of 2026-11-07; backup and restore were not verified, and connection inspection was blocked by IP allowlist restrictions.
- Neon production/staging existed as distinct projects; prior table metadata did not prove business data was populated or that FastAPICloud used the intended branch.
- Tiniest Cloud's Basic Memory trial had expired; do not claim an external memory write succeeded through that service unless it is re-enabled and verified. No subscription or payment action is authorized by this charter.
- Satellite portal was verified as an informational portal, not an owned/operated satellite network.
- Production gates G01–G10 were previously documented as pending external evidence; re-check current evidence before closing any gate.

## 9. Immediate next action

**First:** re-check the Render PostgreSQL resource's current status/expiry and available backup/export paths, then establish an independent backup and prove a restore to an isolated target if authorized and technically possible. If provider restrictions prevent this, record the exact blocker and the smallest owner action needed. Do not upgrade, pay, delete, or change production data to work around the blocker.
