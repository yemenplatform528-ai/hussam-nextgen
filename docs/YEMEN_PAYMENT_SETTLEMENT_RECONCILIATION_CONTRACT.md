# Yemen Payment Settlement & Reconciliation Contract

## Purpose

This layer groups a provider statement into a deterministic reconciliation run before any accounting settlement is accepted.

## Boundary

`Provider Statement → normalized rows → reconciliation run → classified items → exception closure → settlement`

The input is provider-neutral. Provider-specific adapters normalize into `provider_reference`, `actual_amount`, and `currency`.

A run also carries a `source_reference` and exact `source_sha256`. The same run reference is idempotent only when those source identities match.

## Classifications

- `matched`: internal payment exists and amount/currency match exactly.
- `missing_internal`: provider statement contains a reference with no internal payment.
- `missing_in_provider`: an explicitly supplied expected internal payment was absent from the statement.
- `amount_mismatch`: payment exists but amount differs.
- `currency_mismatch`: payment exists but currency differs.
- `duplicate_provider`: the same internal payment resolves more than once inside a normalized run.

No date-based inference is used to manufacture `missing_in_provider` records. Expected internal references must be supplied explicitly when that comparison is required.

## Settlement gate

A reconciliation run may close only when its status is `matched` and its exception count is zero. Settlement remains an accounting operation and is not performed by the reconciliation importer itself.

This preserves the existing rule that provider integrations do not write authoritative finance directly. Database work is committed transactionally using the project's SQLAlchemy session model.

## Current implementation status

Engineering contract implemented and covered by automated tests. No real provider statement or external settlement evidence is claimed by this layer.
