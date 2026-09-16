# G05 — Logistics + Carrier Lifecycle Engineering Closure

Status: `ENGINEERING_READY`

Production certification status: `PENDING_EXTERNAL`

## Scope

This closure establishes a provider-neutral shipment and carrier lifecycle boundary without claiming a live carrier certification.

Implemented engineering controls include:

- tenant-scoped shipment creation and lookup;
- shipment origin validation against the fulfilled sales order warehouse;
- duplicate shipment reference and tracking-number protection;
- ordered shipment state machine;
- tracking-number requirement before physical transit states;
- immutable tracking number after assignment;
- idempotent shipment lifecycle events;
- COD collection only after delivery and only for the exact configured amount/currency;
- provider-neutral carrier registration per tenant;
- carrier webhook/event ingestion with HMAC-SHA256 verification;
- constant-time signature comparison;
- external carrier event idempotency keyed by tenant + carrier + external event id;
- payload hash protection against replay with altered content;
- carrier status mapping into the internal shipment lifecycle;
- carrier webhook secrets kept outside the database and resolved from runtime secret injection;
- carrier and shipment tenant isolation;
- outbox events for shipment lifecycle facts.

## Verification

- Full test suite: `190 passed`.
- Python compileall: passed.
- Fresh SQLite Alembic upgrade through `0004_carrier_lifecycle`: passed.
- `alembic check`: passed with no pending operations.
- `scripts/baseline_audit.py`: `0 failures / 0 warnings`.
- No production carrier credentials, webhook secrets, or external evidence are stored in this candidate.

## External evidence still required for G05 closure

1. A real staging/production carrier account or carrier test environment.
2. Approved carrier integration configuration and endpoint registration.
3. Secret-manager reference proving the webhook secret is injected without source/repository exposure.
4. A real signed carrier webhook delivered to the deployed endpoint.
5. Evidence of signature rejection for an invalid signature.
6. Evidence of idempotent processing of the same external event.
7. Evidence of real shipment state progression through the carrier lifecycle.
8. Evidence that carrier events cannot cross tenant boundaries.
9. Evidence of delivery and COD collection reconciliation where COD is used.
10. External artifacts, SHA-256 hashes, reviewer decision, and Evidence Protocol validation.

G05 is not `CLOSED` until those external artifacts are captured and reviewed.
