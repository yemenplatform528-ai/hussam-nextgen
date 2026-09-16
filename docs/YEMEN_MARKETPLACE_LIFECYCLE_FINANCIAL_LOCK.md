# Yemen Marketplace — Lifecycle & Financial Lock

Status: ENGINEERING LOCKED

This lock closes the Marketplace operational lifecycle after Product Core, Commerce Transaction, and Fulfillment/Settlement.

## Closed boundary

- Returns and item-level returns inherit the immutable Marketplace Order market.
- Disputes inherit the immutable Marketplace Order market.
- Payouts inherit the immutable Marketplace Order market.
- Existing lifecycle rows are backfilled from their Marketplace Order market during migration `0009_marketplace_lifecycle_financial_isolation`.
- Refund completion updates unpaid payout exposure: full refunds reverse held/eligible payouts; partial refunds reduce gross/net payout exposure without changing the platform commission rule.
- Paid payouts are never silently rewritten by a refund; a recovery event is emitted instead.
- Payout eligibility is blocked for refunded, partially-refunded, or disputed orders.
- Payout market mismatch is fail-closed.
- Return/dispute/payout market identity is indexed and foreign-keyed to `market_contexts`.

## Explicit boundary

This lock does not claim live payment-provider execution, live bank/wallet settlement, external payout execution, national logistics coverage, or legal certification. Those remain provider/external verification boundaries.

## Verification

- 234 non-browser tests passed.
- Browser E2E passed independently.
- Lifecycle targeted suite passed.
- `compileall` passed.
- `baseline_audit.py`: 0 failures, 0 warnings.
- Alembic fresh upgrade, downgrade to `0008`, re-upgrade, and `alembic check` passed on SQLite.
- PostgreSQL metadata compilation path executed successfully.
