# Render Operator Capability Map

**Purpose:** expand the operator's practical use of Render before resuming service-readiness work. This document describes capabilities actually exposed in the connected session; it does not claim full account control.

## Current control plane

Workspace: `My Workspace` (`tea-db0p6749v7es73ceig1g`).

### Available through the connected Render tools

| Capability | Available operations | Boundaries |
|---|---|---|
| Workspace/resources | List workspaces, web services/static sites, PostgreSQL and Key Value resources | Resource listing only covers the authenticated workspace |
| Service inspection | Read service configuration and deployment metadata | Not every dashboard setting is exposed |
| Release operations | List deployments, inspect deployment details, trigger deployment | A trigger is a real external action; do not use without a validated target and rollback plan |
| Events and logs | Read service event history, application/request/build logs, discover log label values | Event API covers services, not database/KV event history; log history is bounded/paginated |
| Observability | Query CPU, memory, HTTP request count/latency, instance count, bandwidth, DB/KV active connections | Empty series are inconclusive, not proof of downtime or zero traffic |
| PostgreSQL | Read instance metadata; run read-only SQL if the database network allowlist permits the tool host | No write SQL, backup/restore orchestration, allowlist mutation or credential retrieval |
| Environment variables | Merge/update variables without retrieving existing values | Secrets must never be echoed, copied into Git, or replaced wholesale without an explicit safe plan |
| Resource creation | Create supported web/static/cron services, PostgreSQL and Key Value resources | Connector supports only a subset of Render configuration; resource creation can incur cost and must not be used as a test |
| Deployment notifications | Read service notification setting where surfaced | Cannot manage the whole account's notification policy from this tool set |

## Verified current inventory (2026-10-22)

- `hussam-ai-inference-bridge` — `srv-db7s8m9srm7s73cras7g`, free Node web service, branch `hussam-ai-standalone-portal`.
- `hussam-ai-standalone-portal` — `srv-db7rat2j9qps73dfhmc0`, static site, same repository/branch as the inference service.
- `yemen-satellite-zero` — `srv-db46af3bc2fs73ap868g`, static site, branch `yemen-satellite-zero`.
- `yib-world-independent` — `srv-db39ggid0e5s73fihh1g`, free Node web service, branch `yib-world-independent`.
- `yib-world-independent-memory` — `dpg-db3v8m942hec73f6k260-a`, PostgreSQL 18, Free plan, status available, recorded expiry 2026-11-07.
- No Render Key Value instance was returned by the workspace inventory query.
- All four services use `yemenplatform528-ai/hussam-nextgen`. Branch separation alone is not repository, permission, or data isolation.

## Not exposed by this connected tool set

- Arbitrary shell/SSH execution inside a Render runtime.
- Direct arbitrary HTTP GET/POST smoke tests from the Render tool namespace.
- Complete read/write access to every service setting (domains, disks, autoscaling, health-check configuration, networking and other dashboard fields).
- Database backup/export/restore orchestration and backup-retention controls.
- Account/team/member/role management, billing settings, invoices, and subscription changes.
- Full control of private networking, firewall/IP allowlists, domains, custom certificates, and every resource type.
- Full browser-based end-to-end testing.

These are integration boundaries, not claims that Render itself lacks the features.

## How to expand actual capability safely

1. **Identify the authorized control channel.** Prefer an officially supported Render API integration with narrowly scoped access. Do not paste an API token into chat, source code, issues, logs or documentation.
2. **Keep credentials in a secret manager or the connector's protected credential configuration.** Never commit Render API tokens, database URLs, provider keys, passwords or session secrets to the repository.
3. **Add read-only coverage first:** account/workspace resources, service settings, domains, environment-variable names/status without values, deploy history, logs, metrics, PostgreSQL/KV metadata and billing/usage visibility if supported by the approved integration.
4. **Add controlled write operations only after review:** environment-variable updates, deploy/rollback, domain/network changes, resource create/delete and database changes should be separate, auditable actions with target confirmation and a rollback plan.
5. **Add a real execution channel** for bounded commands and HTTP smoke tests only through an authorized, online host or officially supported runtime/SSH facility. The currently registered Desktop Commander devices were all offline in this session.
6. **Prove each capability with harmless read-only tests**, record exact tool, target, timestamp and result, and label unavailable/blocked operations instead of assuming they work.
7. **Keep costs at $0 unless the owner explicitly approves otherwise.** Do not create paid resources, upgrade plans, activate billing or run quota-consuming model tests as a capability probe.

## Operator rules

- Read before write; inventory the exact target before every mutation.
- No production deployment, secret change, network exposure, destructive database action, paid resource or billing change without a specific safe plan and explicit authorization.
- Never report a successful HTTP test, backup, restore, deploy, or inference unless its result is directly observed.
- A service's `live` deployment status is deployment evidence, not proof that the application is healthy or the external model is responding.
- Keep projects independent where required; do not treat branches in one repository as complete isolation.
- Use evidence labels: VERIFIED, OBSERVED, REPORTED, INFERRED, BLOCKED, UNKNOWN.

## Immediate next capability phase

1. Discover whether an authorized Render API credential/integration can be added to the existing tool environment without exposing it in chat.
2. Map supported API endpoints to a permission matrix; keep account/billing and destructive operations read-only or disabled by default.
3. Add read-only domain/configuration visibility and safe HTTP test capability where the approved connector supports them.
4. Establish a secure execution route independent of Codespaces, then validate with a no-secret health request.
5. Only after those capabilities are verified, resume the postponed service readiness and recovery work.
