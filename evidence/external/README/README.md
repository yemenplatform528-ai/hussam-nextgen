# Hussam NextGen — External Production Evidence Pack

This directory is intentionally empty of fabricated production evidence.

## Rule
A gate closes only when a real external evidence artifact is placed in this directory, hashed, reviewed, and registered through `scripts/production_evidence_protocol.py`.

## Required envelope
Each gate requires `<gate-key>.json` beside its referenced artifact. The artifact path is relative to this directory.

Required envelope fields:
- gate
- environment
- source
- performed_at
- result = PASS
- reviewed_by
- checks: non-empty list
- artifact.path
- artifact.sha256

## Gate keys
- identity_oidc
- postgresql
- payments
- accounting
- logistics
- browser_mobile_e2e
- security
- backup_dr_observability
- operations
- legal_compliance

## Current certification boundary
Repository engineering evidence is complete enough to proceed to external certification. No external gate is declared closed by this pack.
