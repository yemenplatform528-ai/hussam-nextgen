# Hussam NextGen — Final Release / Baseline Lock Protocol

## Purpose

The final lock is a controlled transition from an engineering-complete candidate to a production-certified release. It must be impossible to reach a false PASS from local configuration, mocks, screenshots, or developer-declared status.

## Required sequence

1. Freeze the intended release commit.
2. Run the complete CI workflow on that exact commit.
3. Preserve trusted CI evidence and provenance.
4. Execute the real G01–G10 evidence protocol.
5. Validate every external evidence envelope with `scripts/production_evidence_protocol.py`.
6. Require the evidence manifest to report `closed=10` and `pending_external=0`.
7. Generate a fresh release manifest from the exact release tree.
8. Verify no secrets or prohibited evidence are present.
9. Execute `scripts/final_release_gate.py` against the exact commit, evidence manifest, release manifest, and trusted CI evidence.
10. Create the final release artifact and record SHA-256.
11. Record reviewer/release decision.
12. Tag/lock the exact commit only after all gates pass.
13. Preserve rollback target and migration compatibility evidence.

## Hard prohibitions

The final gate must fail if:

- any G01–G10 gate is pending;
- evidence is missing or its SHA-256 does not match;
- evidence comes only from a mock/local substitute where real execution is required;
- CI evidence belongs to a different commit;
- the release manifest does not describe the intended tree;
- credentials, tokens, payment-card data, private identity documents, or provider secrets are included;
- rollback is not defined;
- database migration compatibility has not been verified.

## Current state

As of 2026-09-24, the repository is **not final-locked**.

Engineering gates and trusted CI/browser evidence are substantially closed, but G01–G10 external production evidence remains pending. Therefore the fail-closed release gate must currently return FAIL.

That is intentional and is the correct safe state.

## Post-certification lock record

When the real external gates are complete, the release record must contain:

- exact Git commit SHA;
- release version;
- CI run ID and provenance;
- external evidence manifest SHA-256;
- release manifest SHA-256;
- final artifact SHA-256;
- database migration version;
- rollback target;
- reviewer identity;
- release decision timestamp;
- known limitations/accepted risks.

The lock record becomes the source of truth for future extensions. Core production software is then treated as immutable; subsequent capabilities are introduced through the governed Developer Platform and its validation/promotion lifecycle.
