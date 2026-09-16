# Yemen Marketplace — Fulfillment & Settlement Engineering Lock

## Scope

This lock closes the physical fulfillment event boundary and the order-to-settlement lifecycle after Commerce Transaction Lock.

## Locked invariants

1. Marketplace fulfillment does not own carrier event history; the logistics shipment/event layer is authoritative.
2. Physical fulfillment transitions (`picked_up`, `in_transit`, `out_for_delivery`, `delivered`) are propagated through the logistics transition service.
3. A repeated carrier/webhook event with the same tenant-scoped `event_id` is idempotent and cannot create duplicate shipment events.
4. A logistics transition failure cannot advance Marketplace fulfillment state.
5. Seller/tenant isolation is enforced on fulfillment and shipment operations.
6. Delivery completion remains the gateway to Marketplace order completion and payout eligibility; payout still requires a verified settled payment and verified payout destination before external payment.
7. Returns/refunds/disputes remain downstream financial recovery workflows and do not bypass payment settlement controls.

## Verification

- Marketplace fulfillment idempotency tests pass.
- Full non-browser test suite passes.
- Browser E2E remains a separate clean gate.
- Alembic/model parity and baseline audit remain required gates.

## Status

**ENGINEERING LOCKED**
