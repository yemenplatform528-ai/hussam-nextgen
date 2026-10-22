# Hussam AI — Secure Rollout Runbook

**Status:** HOLD — do not merge or deploy until preflight gates are evidenced.  
**Last reconciled:** 2026-10-22  
**Services:** static portal `hussam-ai-standalone-portal`; backend `hussam-ai-inference-bridge`.  
**Canonical repo:** `yemenplatform528-ai/hussam-nextgen`, branch `hussam-ai-standalone-portal`.

## Current known evidence

- Render metadata identifies two distinct services on the same source branch with auto-deploy enabled. A source push can trigger deployment; do not assume portal and backend switch atomically.
- PR #118 (owner-session boundary) was observed open and unmerged at the last read-back. Its attached evidence reports a successful Gemini response from the live backend, but `GET /api/session/login` returned 404 and the portal had no login UI.
- Required secret names are `HUSSAM_ACCESS_PASSWORD` and `HUSSAM_SESSION_SECRET`. Their presence and validity in the backend environment have not been verified. Never record or print their values.
- One successful chat response does not prove authentication, session security, quota resilience, or that the proposed PR branch is deployed.

## Gate A — review the candidate change

1. Read PR #118 diff and CI results at the exact head SHA. Verify tests cover successful login, wrong password, missing configuration, cookie flags, expiry, logout, origin handling, and rate limiting.
2. Verify secrets are managed outside source control and are absent from commits, logs, test snapshots, and client bundles.
3. Verify authentication is enforced server-side on protected routes; hiding a UI control is not access control.
4. Verify unauthenticated access to owner-only status/history/export routes returns 401/403 and errors do not leak secrets or provider payloads.
5. Keep the PR open if any acceptance criterion is not covered or if the live deployment target is ambiguous.

## Gate B — configure secrets safely

1. In the authorized Render dashboard, open the **backend** service environment settings.
2. Add `HUSSAM_ACCESS_PASSWORD` and `HUSSAM_SESSION_SECRET` using strong, unique values generated locally or by the host's secret manager. Do not paste values into ChatGPT, issues, commits, terminal history, or logs.
3. Confirm only the variable names are present; do not export or print values. Record any required restart/redeploy.
4. Determine the exact portal origin from its configured production URL and verify the backend allowed-origin setting is exact and minimal. Do not guess or broaden credentialed CORS to `*`.
5. Do not rotate existing credentials blindly; understand dependencies and define rollback first.

## Gate C — coordinated reversible rollout

1. Record each service's currently live deploy ID, source SHA, health, and rollback target.
2. Confirm the backend can deploy the new route without breaking the existing portal. Prefer a backward-compatible backend-first rollout, then portal rollout; document any different sequence.
3. Merge/deploy only after owner-approved secret configuration is verified by variable name, CI is green for the exact head SHA, and rollback targets are recorded.
4. Wait for both services to report completed/live deploys; record actual source SHAs and deploy IDs.
5. Verify the portal in a browser. Confirm login UI, successful login, failed login, session persistence, logout, expired/invalid session, and no sensitive data in browser storage.
6. Use one non-sensitive authenticated smoke test. Verify protected endpoints reject requests without a session and accept only a valid session. Avoid provider-generation requests unless necessary; they may consume quota.
7. Check health and logs, but sanitize output. Never copy cookies, session tokens, passwords, or provider keys into the evidence ledger.

## Rollback

- If either service fails health checks, login fails, or versions are incompatible, stop rollout.
- Roll back the affected service to its recorded prior live deployment; re-test portal and backend together.
- Do not delete secrets or change ownership during rollback. If exposure is suspected, contain it and rotate through host secret settings with a recovery plan.
- Record failure, deploy IDs, rollback action, and post-rollback results.

## Acceptance record

- UTC timestamp:
- PR and head SHA:
- Backend deploy ID/SHA:
- Portal deploy ID/SHA:
- Required variable names present (values never recorded): yes/no/unknown
- CI results for exact SHA:
- Login success / wrong password / logout / expiry:
- Protected route without session:
- Protected route with valid session:
- Browser storage/privacy check:
- Origin/CORS check:
- Rollback target recorded and available:
- Outcome: PASS / FAIL / BLOCKED
- Remaining blockers and evidence links:

**Stop condition:** If secret presence, deployment provenance, or a reversible rollback cannot be verified, leave the PR open and do not claim production authentication is enabled.
