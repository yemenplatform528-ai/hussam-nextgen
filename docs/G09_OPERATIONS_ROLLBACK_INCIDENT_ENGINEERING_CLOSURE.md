# G09 — Operations, Rollback & Incident Drills — Engineering Closure

## Scope
This document closes the **engineering implementation** for Gate G09. It does not claim an external production certification.

## Implemented controls
- Provider-neutral operational objectives with explicit RTO/RPO values.
- Immutable application release artifact identity using version + SHA-256.
- Rollback validation that forbids automatic database downgrade.
- Migration-compatible application rollback; incompatible migrations require a verified backup restore under incident approval.
- Ordered incident lifecycle:
  `DETECTED → TRIAGED → CONTAINED → RECOVERED → VALIDATED → CLOSED`.
- Structured incident action audit trail with actor, action, outcome and timestamp.
- Deterministic secret-free incident/rollback drill harness: `scripts/incident_drill.py`.
- Operational ownership is represented by non-identifying placeholders; real on-call assignments belong to external operations evidence.
- Deployment checklist and evidence capture rules are documented below.

## Deployment checklist
1. Identify immutable release version and artifact SHA-256.
2. Verify migration compatibility before rollout.
3. Run migration as a separate controlled job; do not combine it with application rollback.
4. Deploy the immutable application artifact.
5. Verify `/health` and `/ready`.
6. Verify authentication, critical commerce, payment and observability smoke paths.
7. Record deployment artifact/version and reviewer decision.

## Rollback checklist
1. Stop the new rollout and preserve request/audit/outbox evidence.
2. Select the previously approved immutable application artifact.
3. Confirm database schema compatibility with that artifact.
4. Roll back application binaries/configuration only when compatible.
5. Never automatically downgrade the database.
6. If incompatible, invoke the approved backup/restore recovery procedure under incident control.
7. Verify health/readiness and critical smoke journeys.
8. Record outcome, timestamps, operator/reviewer and artifact hashes without secrets.

## Incident drill
The engineering harness exercises the complete state machine and records a secret-free audit trail. It is a simulation, not a production incident certification.

```text
python scripts/incident_drill.py --output /tmp/hussam-g09-incident-drill.json
```

## RTO/RPO linkage
G09 consumes the approved service RTO/RPO objectives. G08 supplies backup/restore and observability evidence. A production G09 closure must show that the tested rollback/incident procedure operates within the approved objectives, using measured external timings rather than repository assumptions.

## External evidence required for CLOSED
- Named operational ownership/on-call process.
- Real deployment and rollback drill in the production-like environment.
- Real incident exercise with measured recovery time and recovery point.
- Incident ticket/timeline and reviewer decision.
- Deployment and rollback artifacts with SHA-256.
- Evidence that no database downgrade was performed and any restore was controlled.

**Status: ENGINEERING_READY / PENDING_EXTERNAL**
