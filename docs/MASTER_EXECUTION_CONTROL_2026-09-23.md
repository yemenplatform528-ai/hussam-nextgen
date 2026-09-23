# Hussam NextGen — Master Execution Control
## Controlled project state — 2026-09-23

### Authority
This document is the execution-control companion to the canonical engineering baseline. It does not replace source code, release manifests, or the external certification record.

### Current source of truth
- Repository: `yemenplatform528-ai/hussam-nextgen`
- Default branch: `main`
- Current `main`: `2b015294332406d2b82180d215ec75f001c57f92` — browser E2E cold-start timeout adjustment only.
- Canonical engineering baseline remains: `473cb7785bf2853e884a3ed28ea17f18d5085efa`
- Current delta remains limited to deployment configuration, CI/dependency/security maintenance, PostgreSQL migration hardening, and browser-test reliability.
- No Marketplace, AI, HUS, or external-gate business behavior was intentionally changed.

### Verified engineering boundary
The repository's latest recorded engineering verification states:
- baseline audit: 0 failures / 0 warnings
- public route audit: 202 routes
- Amazon public-scope audit: 30/30 capability families closed
- Yemen payment-provider matrix: fail-closed/provider-neutral
- UI audit: PASS
- compileall: PASS
- deterministic release manifest: PASS
- migration verification through 0028: PASS
- 361/361 tests executed successfully in bounded partitions
- external certification remains pending
- CI run `35916704955` for current `main` completed with all three jobs successful: baseline, PostgreSQL integration, and container-security.
- The PostgreSQL migration gate exposed and closed two real blockers: long Alembic revision IDs on PostgreSQL and a non-idempotent shipping constraint migration.

These repository gates are verified; external certification is still separate.

### External runtime verification
- FastAPI Cloud staging app: `https://hussam-nextgen.fastapicloud.dev/`
- The app was provisionally marked Live/Ready by FastAPI Cloud for deployment `6f4fe32f-7027-4380-bd98-f825744ee60d`, commit `80af87f70127872ef6fcfe730b2e6c015bfb722b`.
- Direct runtime access from this execution environment is unavailable, so that dashboard state is not being treated as endpoint-level evidence.
- A repository-owned external smoke workflow is now part of the certification path. It verifies `/health`, `/openapi.json`, and `/docs` from a GitHub-hosted runner after every `main` push and can also be dispatched manually.
- `/ready` is intentionally not part of the public smoke success criterion until a real PostgreSQL staging database is attached. In staging, deep readiness must be backed by a reachable PostgreSQL database.
- No deployment platform is considered production-active until database-backed runtime evidence exists.

### External gate register
G01 Identity/OIDC — PENDING_EXTERNAL
G02 PostgreSQL/Recovery — PENDING_EXTERNAL
G03 Payments — PENDING_EXTERNAL
G04 Accounting — PENDING_EXTERNAL
G05 Logistics — PENDING_EXTERNAL
G06 Browser/Mobile — PENDING_EXTERNAL
G07 Security — PENDING_EXTERNAL
G08 DR/Observability — PENDING_EXTERNAL
G09 Operations — PENDING_EXTERNAL
G10 Legal/Compliance — PENDING_EXTERNAL

No gate may be promoted by configuration, mocks, screenshots alone, local tests, or generated evidence.

### Infrastructure decision
- `render.yaml` remains the free Docker fallback and defines `/ready` as the health check.
- Render signup remains blocked by its CAPTCHA surface.
- FastAPI Cloud remains the first staging candidate because it supports GitHub-triggered deployments and environment secrets. Its documentation confirms that only default-branch pushes trigger GitHub deployments and that secrets can be stored encrypted. 
- The application intentionally reports `/ready` as not ready until `DATABASE_URL` exists and, in staging, until PostgreSQL is reachable. This is fail-closed behavior.
- The next required external action is therefore database attachment, not another application-code rewrite.

### GitHub CI decision
The required repository CI remains:
1. locked dependency installation
2. editable package installation
3. baseline audit
4. compileall
5. tests
6. SQLite migration and Alembic drift check
7. deterministic manifest
8. pip consistency
9. pip-audit
10. PostgreSQL migration/schema/integration tests
11. Docker build and HIGH/CRITICAL Trivy scan

The new external runtime smoke workflow is intentionally separate from the core CI gate so an external hosting outage cannot falsely imply a repository regression.

### Connection capability matrix
| Surface | Capability | Project decision |
|---|---|---|
| GitHub | Read/write repository, branches, commits, PRs, workflow inspection | Primary execution surface |
| GitLab | Operational account/project/CI access | Secondary only; no migration |
| Render | Free Git/Docker staging | Fallback; current signup CAPTCHA blocks progress |
| Neon | PostgreSQL suitable for staging | Use only after connector/project access is actually verified |
| Auth0 | Suitable free OIDC provider | Use for G01 only when a real account/application can be created |
| FastAPI Cloud | Free Hobby, GitHub deployment, encrypted environment secrets | First staging candidate |
| Local/Codespace | Real git push previously verified | Fallback execution surface, not the canonical control plane |

### Execution order
1. Verify FastAPI Cloud public runtime through the new GitHub-hosted smoke workflow.
2. Attach a real PostgreSQL staging database and configure `DATABASE_URL` as a FastAPI Cloud secret.
3. Verify `/ready` against that database and record evidence.
4. Establish/verify HTTPS callback behavior.
5. Execute G01 against a real OIDC provider.
6. Produce artifact-backed evidence for G02–G10 in order.
7. Perform final release/audit lock.
8. Only then enter Yemen production implementation.

### Yemenization boundary
Yemen-specific work is not permitted to mutate the frozen Sovereign Core, Marketplace, AI, or HUS without a concrete defect or approved architecture change.

The Yemen layer will be implemented as explicit market configuration/adapters for:
- geography and address hierarchy
- currency/display and exchange-rate handling
- local payment/wallet/bank adapters
- logistics/carrier/pickup/service areas
- connectivity-aware operation
- local seller/customer workflows
- local policy/compliance requirements

### Free-first constraint
No paid subscription, trial, credit purchase, or paid infrastructure is required as a prerequisite for the next engineering step. Free options are preferred, and trial activation is avoided unless a concrete blocker cannot be solved otherwise.

### Stop conditions
Stop and escalate to the user only when an external account, credential, human approval, or real-world contract is strictly required and cannot be executed through connected tools. Ask for one narrowly scoped action, then resume ownership of the remaining work.

### Release discipline
The project is not declared production-ready until the external certification record contains real evidence envelopes for all applicable gates, artifact hashes match, rollback is prepared, and the final release decision is explicitly recorded.
