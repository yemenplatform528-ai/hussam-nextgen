# Yemen Marketplace — Market Isolation Engineering Lock

## Purpose

Marketplace is a product layer over the locked Yemen Foundation. Market context is authoritative for marketplace presentation and transaction scope; seller identity remains tenant-scoped and reusable across markets.

## Closed invariants

1. Product, Offer, Listing, Cart, Customer Order, Marketplace Order, Fee Rule, Shipping Rate, Shipping Quote and Offer Competition carry market context.
2. Product/Offer/Listing creation resolves an explicit market when more than one active market exists.
3. Currency used by Marketplace must be enabled in `market_currencies` for the selected market.
4. Public discovery is market-filtered and cannot silently return another market's listing.
5. Public product/offer views accept market context and reject a product outside that market.
6. Checkout is bound to the cart market; a shipping address from another market is rejected.
7. A buyer can maintain independent active carts per market; cart operations are never silently switched across markets.
8. Legacy addresses without market context may be assigned during non-production compatibility flows only when the transaction context is unambiguous; production rejects ambiguous legacy address context.
9. Shipping rates carry structured `governorate_id`, `district_id`, and `locality_id` references when available; those references are validated against the selected market and hierarchy. Free-text geography remains a legacy compatibility representation, not the authoritative relationship.
10. Production shipping rates and addresses require structured governorate context; development/test compatibility may resolve unambiguous names.
11. Shipping quotes are market-bound and cannot be consumed by a different market checkout.
12. Fee-rule selection is market-scoped; legacy null-market rules are compatibility-only and are not a substitute for explicit production market configuration.
13. Offer competition is market-scoped; the same catalog group can have independent competition state per market.
14. Migration `0006_marketplace_market_isolation` fails closed when existing marketplace rows cannot be assigned to exactly one active market.
15. Migration `0007_marketplace_shipping_geography_and_cart_scope` closes structured shipping geography fields and per-market cart uniqueness, with upgrade/downgrade verification.

## Deliberate boundaries

- Seller profiles remain tenant-scoped, not market-scoped.
- Catalog groups remain reusable product identity; competition is market-scoped.
- Yemen geography, currency configuration and provider registry remain Foundation responsibilities.
- Payment execution, provider credentials and logistics execution remain outside this lock.
- Legacy free-text shipping geography is retained only for compatibility with existing rows; new production configuration is structured.

## Verification

- 226 tests total: 225 non-browser tests PASS + browser E2E PASS independently.
- `compileall`: PASS.
- `baseline_audit.py`: 0 failures / 0 warnings.
- SQLite migration: `upgrade -> check -> downgrade -> upgrade -> check`: PASS.
- PostgreSQL metadata DDL compilation: PASS (395 compiled statements).
- Targeted Marketplace/Y2 isolation suite: 44 tests PASS.

## Environment note

`pip check` still reports the pre-existing unrelated `moviepy`/`pillow` environment conflict; it is not introduced by Marketplace isolation.
