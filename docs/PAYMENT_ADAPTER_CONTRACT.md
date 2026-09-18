# Payment Adapter Contract

**Status:** engineering contract — no provider integration is certified by this document.
**Updated:** 2026-09-18

The adapter boundary translates a provider's API/file protocol into a small provider-neutral contract. The core payment service remains authoritative for payment state, reconciliation, settlement, and accounting.

## Operations

1. `create` — initiate a payment and return the provider payment identity.
2. `get_status` — query provider state without writing Hussam state directly.
3. `refund` — request a provider refund and return the provider refund identity.
4. `import_statement` — normalize a provider statement into immutable statement rows for the reconciliation layer.

## Hard boundaries

- Adapter code must not write journals or ledger entries.
- Adapter code must not mutate `PaymentIntent`, settlement, or reconciliation records directly.
- Credentials/secrets stay outside the core database and source tree.
- Provider-specific statuses are translated at the adapter boundary; the core consumes neutral statuses.
- Statement import must preserve the provider reference, amount, currency, and source identity needed for reconciliation.
- An unconfigured or uncertified provider fails closed; the catalog entry alone is never treated as an active rail.
- Production activation requires the provider evidence/certification gates in `docs/YEMEN_PAYMENT_PROVIDER_CERTIFICATION_MATRIX.md`.

## Yemen rollout rule

Al-Kuraimi, Al-Qutaibi/Shalan, Al-Najm, YPCC, banks, wallets, and exchange/payment rails can each receive an adapter implementation only after the relevant technical and operational evidence exists. The contract deliberately does not claim that any provider currently has a working Hussam adapter.
