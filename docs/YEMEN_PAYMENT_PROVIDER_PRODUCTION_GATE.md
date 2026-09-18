# Yemen Payment Provider Production Gate

**Status:** engineering contract — no provider is currently certified by this document.
**Updated:** 2026-09-18

The payment adapter may exist before a provider is production-enabled. Execution is
allowed only when the provider registry, market capability, and complete production
evidence all agree.

## Required conditions

1. Provider exists in `provider_registry_entries`.
2. Provider status is exactly `production`.
3. Integration mode is not `none`.
4. An active `ProviderMarketCapability` exists for the requested market/capability/rail/currency.
5. All 11 evidence flags are explicitly `true`:
   - identity/licensing
   - capability
   - market/currency scope
   - commercial basis
   - technical interface
   - authentication
   - webhook semantics
   - idempotency
   - settlement/reconciliation
   - certification
   - operational owner

Missing, malformed, or partial evidence blocks execution. Public capability evidence alone
never satisfies the gate.

## Separation of authority

The gate authorizes the adapter boundary only. It does not authorize ledger posting,
settlement approval, or provider certification by itself. Those remain separate controls.
