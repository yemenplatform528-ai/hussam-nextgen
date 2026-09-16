# External Production Evidence Checklist

This checklist is intentionally operational. It distinguishes repository engineering from evidence that must come from real infrastructure, providers, contracts, or approved review.

| Gate | Evidence required to close | Owner / source | Closure condition |
|---|---|---|---|
| Identity/OIDC | production issuer metadata, client registration, secret-manager reference, successful browser login/logout/session-refresh evidence | Identity operator | reproducible login journey succeeds in production-like environment |
| PostgreSQL | real PostgreSQL instance, migration output, `alembic check`, backup artifact, restore artifact, integrity query | Platform operator | restore completes and application passes smoke checks against restored DB |
| Payments | provider certification, signed webhook samples, idempotency evidence, capture/refund/settlement/reconciliation evidence | Payment provider + platform | end-to-end transaction reconciles without manual database mutation |
| Accounting | real ledger adapter, account mapping approval, posting/reversal/reconciliation evidence | Finance operator | ledger totals reconcile with payment/order settlement data |
| Logistics | carrier contract/test credentials, shipment creation, tracking callbacks, delivery/exception evidence | Logistics operator | end-to-end shipment lifecycle succeeds |
| Browser/mobile E2E | browser traces/screenshots/video and device smoke artifacts for customer, seller and admin journeys | QA operator | critical journeys pass on supported targets |
| Security | CI dependency/image reports, edge rate-limit configuration, external assessment/penetration report | Security operator | no unaccepted critical/high findings and controls evidenced |
| Backup/DR/Observability | restore drill report, alert firing evidence, dashboards, recovery-time/recovery-point measurements | SRE/operator | drill meets declared RTO/RPO and alerts are actionable |
| Operations | on-call ownership, support workflow, rollback drill, incident drill, deployment checklist | Operations owner | incident/rollback exercises completed and documented |
| Legal/Compliance | marketplace terms, seller agreement, privacy, returns/refunds, prohibited goods, tax/compliance review | Legal/compliance owner | written approval for launch jurisdictions |

## Evidence rule

Do not replace evidence with environment-variable presence, mocked providers, unit tests, or screenshots of configuration. A gate is closed only when the named evidence is reproducible and attributable to the real external system or approved operational process.
