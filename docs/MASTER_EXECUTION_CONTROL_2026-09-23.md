# Hussam NextGen — Master Execution Control
## Controlled project state — 2026-09-23

### Authority
This document is the execution-control companion to the canonical engineering baseline. It does not replace source code, release manifests, or the external certification record.

### Current source of truth
- Repository: `yemenplatform528-ai/hussam-nextgen`
- Default branch: `main`
- Current main commit: `1c3991b63c779e54fe13eddf6cd9dec5559bd9aa`
- Canonical engineering commit: `473cb7785bf2853e884a3ed28ea17f18d5085efa`
- Delta from canonical: packaging/CI discovery fix only.
- No Marketplace, AI, HUS, database, or external-gate behavior was intentionally changed by the delta.

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

These are repository records, not newly re-executed evidence in this control document.

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
The application is structurally prepared for Git-backed Docker deployment:
- `render.yaml` defines a free staging web service and `/ready` health check.
- `scripts/render_start.sh` applies migrations before starting Uvicorn.
- Render supports GitHub-backed Docker web services, HTTPS/TLS, and a free web-service tier; its free tier is explicitly for testing/preview rather than production.
- FastAPI Cloud currently advertises a free Hobby plan with no credit card required and GitHub-triggered deployment. It is an alternative staging path worth testing if Render account access remains blocked.
- No deployment platform is considered active until a real deployed URL and runtime evidence exist.

### GitHub CI decision
The CI workflow is present and includes:
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

The connector currently exposes no verified green push-run result for `main`. Therefore CI status is **UNVERIFIED**, not PASS and not FAIL.

### Connection capability matrix
| Surface | Capability | Project decision |
|---|---|---|
| GitHub | Read/write repository, branches, commits, PRs, workflow inspection | Primary execution surface |
| GitLab | Operational account/project/CI access | Secondary only; no migration |
| Render | Free Git/Docker staging | Primary deployment candidate; account CAPTCHA is external |
| Neon | PostgreSQL suitable for staging | Use only after connector/project access is actually verified |
| Auth0 | Suitable free OIDC provider | Use for G01 only when real account/application can be created |
| FastAPI Cloud | Free Hobby, GitHub deployment | Secondary deployment candidate if Render remains blocked |
| Local/Codespace | Real git push previously verified | Fallback execution surface, not the canonical control plane |

### Execution order
1. Resolve the first real staging deployment without changing the application architecture.
2. Attach a real PostgreSQL staging database.
3. Establish HTTPS.
4. Execute G01 against a real OIDC provider.
5. Produce artifact-backed evidence for G02–G10 in order.
6. Perform final release/audit lock.
7. Only then enter Yemen production implementation.

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
