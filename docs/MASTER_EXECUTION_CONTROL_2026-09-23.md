# Hussam NextGen — Master Execution Control
## Controlled project state — 2026-09-24

### Authority
This document is the execution-control companion to the canonical engineering baseline. It does not replace source code, release manifests, or external certification evidence.

### Current source of truth
- Repository: `yemenplatform528-ai/hussam-nextgen`
- Default branch: `main`
- Current `main`: `adaf854c59f9259f3d263373a86c6489d4d8915a`
- Canonical engineering baseline remains: `473cb7785bf2853e884a3ed28ea17f18d5085efa`
- The certification-control delta remains limited to deployment/CI configuration, dependency/security maintenance, PostgreSQL migration hardening, and external verification workflow.
- Marketplace, AI, HUS, and sovereign-core business behavior remain protected by the certification boundary.

### Verified engineering boundary
Latest verified engineering CI:
- Run: `35920819845`
- Conclusion: SUCCESS
- Baseline job: SUCCESS
- PostgreSQL integration job: SUCCESS
- Container-security job: SUCCESS
- The run covered locked dependency installation, package installation, repository audit, compileall, tests, fresh SQLite migration, Alembic drift, release manifest, dependency consistency, dependency vulnerability audit, PostgreSQL migration/schema/integration, Docker build, and HIGH/CRITICAL container scan.

Latest public runtime smoke:
- Run: `35920819812`
- Conclusion: SUCCESS
- Verified public staging endpoints: `/health`, `/openapi.json`, `/docs`
- This proves public runtime smoke only; it does not prove database-backed readiness or production readiness.

### External readiness boundary
- FastAPI Cloud staging: `https://hussam-nextgen.fastapicloud.dev/`
- Neon staging resource: `hussam-nextgen-staging` — user-confirmed attached to the FastAPI Cloud app.
- Repository-owned readiness workflow: `.github/workflows/external-readiness.yml`
- Latest readiness workflow: `35920819802`
- The workflow completed and uploaded sanitized evidence, but the public `/ready` probe was blocked by Cloudflare Error 1010 / browser-signature access control.
- This is an external access-control result, not evidence that PostgreSQL is unavailable.
- Cloudflare documents Error 1010 as an owner-configured browser-signature block and directs the site owner to adjust the relevant security setting. No bypass/spoofing is permitted in this certification process.
- Therefore G02 remains PENDING_EXTERNAL until trustworthy database-backed readiness evidence is obtained through an owner-approved/platform-side path.

### External gate register
- G01 Identity/OIDC — PENDING_EXTERNAL — issue #2
- G02 PostgreSQL/Recovery — PENDING_EXTERNAL — issue #11
- G03 Payments — PENDING_EXTERNAL — issue #13
- G04 Accounting — PENDING_EXTERNAL — issue #14
- G05 Logistics — PENDING_EXTERNAL — issue #15
- G06 Browser/Mobile E2E — PENDING_EXTERNAL — issue #16
- G07 Security/Rate Limiting — PENDING_EXTERNAL — issue #17
- G08 DR/Observability — PENDING_EXTERNAL — issue #18
- G09 Operations/Rollback — PENDING_EXTERNAL — issue #19
- G10 Legal/Compliance — PENDING_EXTERNAL — issue #20

No gate may be promoted by mocks, screenshots alone, local tests, generated evidence, or configuration claims.

### Infrastructure decision
- FastAPI Cloud is the active staging surface.
- Neon is the intended real PostgreSQL staging resource.
- Render remains a free fallback but is not being pursued while FastAPI Cloud is viable; its signup CAPTCHA remains an external blocker.
- `/ready` is fail-closed: in staging it requires `DATABASE_URL` and a successful PostgreSQL connection.
- Do not expose, copy, log, or commit `DATABASE_URL` or any other secret.
- No production declaration is permitted from staging smoke alone.

### GitHub CI decision
Core engineering CI remains the repository quality gate. External runtime/readiness workflows remain separate so external hosting failures cannot be misclassified as source regressions.

### Execution order
1. Engineering CI — last verified GREEN baseline is the immediate ancestor; current commit `adaf854c59f9259f3d263373a86c6489d4d8915a` adds only external-readiness evidence sanitization and awaits its own CI result.
2. Public runtime smoke — CLOSED/GREEN for the current staging deployment.
3. Real Neon staging attachment — user-confirmed; platform evidence still required.
4. Database-backed `/ready` — NEXT EXTERNAL GATE; currently blocked by Cloudflare 1010 access control.
5. Establish/verify HTTPS callback behavior.
6. Execute G01 against a real OIDC provider.
7. Close G02 and then execute G03–G10 with artifact-backed evidence, allowing preparation in parallel where it does not weaken gate order.
8. Final release/audit lock.
9. Only after certification/release lock, enter Yemen production and BUILD Phase 1 of Yemenization.

### Yemenization boundary
Yemenization is intentionally downstream of certification. It must not mutate the frozen Sovereign Core, Marketplace, AI, or HUS without an approved architecture change.

The future Yemen layer will use explicit adapters/configuration for:
- geography and address hierarchy
- currency/display and exchange-rate handling
- local payment/wallet/bank adapters
- logistics/carrier/pickup/service areas
- connectivity-aware operation
- local seller/customer workflows
- local policy/compliance requirements

### Free-first constraint
Prefer free capabilities. No paid subscription, trial, credit purchase, or paid infrastructure is a prerequisite for the next engineering step unless a concrete external certification requirement makes it unavoidable.

### Current execution position
- Engineering CI: inherited GREEN on the last verified application/documentation baseline; current workflow-hardening commit is awaiting its own CI result.
- Public runtime smoke: GREEN.
- FastAPI Cloud staging: ACTIVE.
- Neon staging attachment: USER-CONFIRMED.
- `/ready` external evidence: BLOCKED by Cloudflare 1010; G02 remains PENDING_EXTERNAL.
- G01–G10: PENDING_EXTERNAL until real evidence exists.
- No production-ready claim has been made.

### Stop conditions
Escalate only when an external account, credential, human approval, or real-world contract is strictly required and cannot be executed through connected tools. Ask for one narrowly scoped action, then resume ownership of the remaining work.

### Release discipline
The project is not production-ready until all applicable external gates have real evidence envelopes, artifact hashes match, rollback is prepared, and the final release/audit lock is explicitly recorded.
