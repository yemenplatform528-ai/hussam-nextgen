# Yemen Phase 1 — Cross-Capability E2E Gate — 2026-09-24

## Objective

Prove that Yemenization is runtime behavior across shared Hussam capabilities, not merely configuration visible in Market Context.

The E2E gate must exercise one continuous buyer journey and preserve the authority boundaries of the existing engines.

## Required journey

MarketContext → Geography/Address → Catalog → Cart → Connectivity Mutation → Checkout → Payment Method → Order Snapshot → Fulfillment/COD → Order Readback

## Assertions

### Market context
- active Yemen market is resolved;
- Arabic locale and market currency are returned;
- inactive market is rejected.

### Money
- checkout displays YER context;
- no client-side FX conversion occurs;
- authoritative totals remain server-owned;
- no client-supplied platform fee becomes authoritative.

### Geography
- address belongs to the buyer;
- address is bound to the active market;
- coverage is checked before checkout;
- unavailable coverage fails closed.

### Commerce
- cart mutation carries an idempotency key;
- replay does not double-apply the mutation;
- a reused key with a different request is rejected;
- checkout persists the selected payment method.

### Connectivity
- safe public reads can use the local cache;
- offline cart changes are explicitly local/pending;
- online replay reuses the original mutation key;
- offline checkout never creates an order or payment intent.

### COD
- COD is exposed only when the market catalog says it is available;
- COD does not fabricate a provider payment intent;
- the selected COD method is persisted on the order;
- fulfillment carries the authoritative order total into shipment cod_amount;
- existing logistics authority performs delivery transition and collection.

### Audit
- mutation reservation, transition and replay produce durable audit records;
- mutation readback is tenant/actor scoped.

## Negative-path gate

The E2E gate is incomplete if any of these can succeed:

- offline order creation;
- offline payment/ledger mutation;
- duplicate checkout creating two orders;
- duplicate cart mutation applying twice;
- client-side authoritative FX/totals;
- checkout against an unavailable market;
- buyer using another user's address;
- unsupported payment method accepted;
- provider certification inferred from public documentation.

## Evidence package

A successful gate must preserve:

1. exact source commit;
2. CI run ID;
3. browser test output;
4. desktop + mobile execution evidence;
5. API request/response assertions;
6. database assertions for order/payment/COD/mutation/audit state;
7. source and test hashes;
8. environment/runtime version;
9. failure-path results.

This is an engineering gate. It is not a substitute for G01–G10 external production evidence.
