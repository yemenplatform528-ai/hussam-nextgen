# G04 — Accounting + Reconciliation Engineering Closure

## Status

**ENGINEERING_READY — PRODUCTION CERTIFICATION PENDING_EXTERNAL**

This document records engineering closure only. It does not claim that a real production ledger, external accounting system, finance operator review, or production reconciliation run has been completed.

## Implemented controls

- Tenant-scoped double-entry journals with positive balanced postings.
- Open fiscal-period enforcement for posting dates.
- Closed/ambiguous/missing fiscal periods reject posting.
- Tenant-scoped unique journal references.
- Explicit journal posting date retained with the ledger record.
- Journal content hash generated from tenant, reference, currency, posting date, and ordered lines.
- Integrity verification detects post-write journal-line tampering.
- Reversal creates a new journal and preserves the original journal.
- One reversal per original journal is enforced by a unique constraint.
- Cross-tenant journal access/reversal is rejected.
- Tenant-scoped chart-of-accounts registry with account type and optional currency.
- Trial-balance aggregation by account and currency.
- Ledger debit/credit totals can be reconciled as a control invariant.
- Control-account reconciliation reports expected balance, actual balance, delta, and match status.
- Existing payment capture and settlement postings remain inside the same authoritative finance engine.

## Engineering verification

- Full automated suite: **187 passed**.
- Fresh SQLite migration: **0001 → 0002 → 0003 successful**.
- `alembic check`: clean.
- Python compile check: clean.
- Baseline audit: **0 failures / 0 warnings**.

## External evidence still required

1. Real PostgreSQL production/staging ledger database.
2. Approved chart-of-accounts mapping by the finance owner.
3. Real payment/order settlement to ledger reconciliation.
4. Real journal posting, reversal, period close, and recovery evidence.
5. Independent finance-operator review of trial balance and control-account totals.
6. Backup/restore evidence for the accounting database (coordinated with G02/G08).
7. External artifacts with SHA-256 and reviewer decision.
8. Evidence protocol validation before G04 can be marked `CLOSED`.

## Boundary

The accounting engine is the authoritative internal ledger. External providers, marketplace orders, and payment systems must feed it through explicit posting contracts; they do not become the accounting source of truth themselves.
