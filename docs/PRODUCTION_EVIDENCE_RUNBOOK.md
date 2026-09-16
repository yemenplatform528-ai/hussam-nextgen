# Production Evidence Closure Runbook

## Objective

Move Hussam NextGen from engineering-complete to production-proven without introducing a second runtime architecture or a product-version chain.

## Order

1. Identity/OIDC
2. PostgreSQL + migration + restore
3. Payments + signed webhooks + reconciliation
4. Accounting + reconciliation
5. Logistics + carrier lifecycle
6. Browser/mobile E2E
7. Security + distributed rate limiting
8. Backup/DR + observability + alerting
9. Operations + rollback/incident drills
10. Legal/compliance approval
11. Final Amazon public-scope audit
12. Yemenization

## Closure rule

For each gate, perform the real certification run, capture its external artifact, create the matching `<gate>.json` envelope, and run the evidence protocol. Only a validated envelope with a matching SHA-256 can change the gate to `CLOSED`.

Never manufacture evidence from unit tests, mocks, environment-variable presence, local configuration, or screenshots of configuration.

## Yemenization safety

All provider-specific work must remain behind existing contracts/adapters. Yemen-specific implementation begins only after the final Amazon audit and 10/10 evidence closure. This preserves the global Core and avoids rework.
