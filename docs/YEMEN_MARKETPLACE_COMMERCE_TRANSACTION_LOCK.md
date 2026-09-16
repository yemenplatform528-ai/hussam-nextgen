# Yemen Marketplace — Commerce Transaction Lock

## Scope

This lock closes the transaction boundary for the buyer commerce path after Product Core:

`Market → Cart → Checkout → Inventory Reservation → Order → Payment Session → Capture`

## Invariants

1. A buyer may have one active cart per Market; checkout without `market_id` is rejected when multiple active carts exist.
2. Checkout consumes only the selected Market cart and never clears another Market's cart.
3. Managed-product checkout creates Commerce sales orders and inventory reservations inside the Marketplace transaction boundary.
4. A failure in a later seller group rolls back the earlier seller groups instead of leaving a partially-created multi-seller checkout.
5. Payment-session capture creates all seller payment intents inside one transaction boundary; a later allocation failure does not leave earlier payment intents committed.
6. Payment capture remains provider-agnostic and does not authorize a provider to mutate authoritative finance directly.
7. Existing single-market callers remain compatible because the Market can still be inferred when the buyer has exactly one active cart / the system has one active Market.

## Verification

- Marketplace isolation + payment orchestration tests: PASS.
- Full non-browser suite: PASS.
- Browser E2E: PASS.
- Compileall: PASS.
- Baseline audit: 0 failures / 0 warnings.
- Alembic fresh upgrade/check and 0008↔0007 downgrade/re-upgrade: PASS.
- PostgreSQL DDL compilation remains an external-runtime gate; no live PostgreSQL server is assumed by this lock.

This is an engineering transaction lock, not a claim of live payment-provider certification or production financial settlement.
