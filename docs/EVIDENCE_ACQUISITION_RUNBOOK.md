# Hussam NextGen — External Evidence Acquisition Runbook

Reviewed: 2026-09-19

This runbook is the final operational handoff from engineering-complete to independently evidenced production readiness. It does not fabricate or pre-close any gate.

## Order

G01 Identity/OIDC → G02 PostgreSQL → G03 Payments → G04 Accounting → G05 Logistics → G06 Browser/Mobile E2E → G07 Security → G08 Backup/DR/Observability → G09 Operations → G10 Legal/Compliance.

Each gate requires:
- a real environment/source;
- a separately captured evidence artifact;
- SHA-256 of that artifact;
- a JSON evidence envelope;
- reviewer identity and decision;
- validation with `scripts/production_evidence_protocol.py`.

## Evidence directory

Use a controlled directory outside the source tree while collecting evidence, then copy only non-sensitive reviewed artifacts into the repository evidence location. Never store passwords, tokens, payment-card data, private identity documents, or provider secrets.

## Gate checklists

### G01 Identity/OIDC
- issuer/discovery metadata captured from the real issuer
- client registration identifier captured without secret material
- secret-manager reference recorded
- real login and callback E2E executed
- token claims/tenant isolation checked
- artifact reviewed

### G02 PostgreSQL
- real PostgreSQL instance identified
- all migrations applied from a clean database
- schema/version recorded
- backup generated
- restore into a separate database completed
- post-restore smoke and integrity checks passed
- restore timing recorded

### G03 Payments
- provider identity/licensing evidence
- commercial/contract basis
- sandbox or production test account evidence
- create/status/capture/refund lifecycle
- signed webhook verification
- idempotency replay
- settlement/reconciliation statement match
- certification/approval evidence

### G04 Accounting
- external ledger or accounting target identified
- posting mapping verified
- duplicate/replay behavior verified
- reconciliation against source transactions
- exception handling reviewed

### G05 Logistics
- carrier identity and service scope
- create/dispatch/status/delivery/return lifecycle
- tracking/reference mapping
- failure/retry behavior
- proof of delivery or equivalent evidence

### G06 Browser/Mobile E2E
- deployed URL/build identifier
- real browser/device matrix
- authentication journey
- marketplace journey
- payment/settlement-facing journey without exposing sensitive data
- screenshots/video/log artifacts as appropriate

### G07 Security
- production dependency scan
- production image/container scan where applicable
- secret scan
- authentication/authorization checks
- rate-limit evidence in the distributed deployment
- security review/assessment artifact

### G08 Backup/DR/Observability
- backup artifact
- restore artifact
- measured RPO/RTO
- dashboards
- alert delivery proof
- incident/alert acknowledgement

### G09 Operations
- named owner/on-call evidence
- incident workflow
- rollback drill
- deployment/change record
- escalation path
- closure review

### G10 Legal/Compliance
- marketplace terms/policies
- privacy/data handling review
- payment/commercial obligations review
- applicable Yemen/local requirements identified by qualified reviewer
- approval record

## Closure rule

Do not mark a gate CLOSED because a checklist is complete. CLOSED means the evidence artifact exists, its SHA-256 is recorded, the envelope validates, and an authorized reviewer has accepted it.
