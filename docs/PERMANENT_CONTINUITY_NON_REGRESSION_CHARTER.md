# Hussam NextGen — Permanent Continuity & Non-Regression Charter

## Purpose

This charter makes project continuity a first-class engineering requirement.
Hussam NextGen / Yemenization is maintained as a durable Yemen-focused platform,
not as a one-time demo or disposable deployment.

## Canonical authority

- Canonical repository: `yemenplatform528-ai/hussam-nextgen`
- Canonical branch: `main`
- Exact release SHA is the authority for every release.
- External evidence is valid only when attributable to that exact release SHA.
- Basic Memory project `main` is the durable project-memory layer for decisions,
  operating rules, and continuity context.

## Non-regression rules

1. Do not replace the canonical foundation with an unrelated rebuild.
2. Do not silently rewrite history of a locked release.
3. Do not close a production gate without real evidence.
4. Do not turn optional providers, AI, payments, logistics, or communications
   into hidden mandatory dependencies.
5. Do not remove rollback, restore, audit, or provenance paths to make a gate pass.
6. Preserve tenant isolation, financial integrity, idempotency, auditability,
   security boundaries, and recovery controls.
7. Every material change must be attributable to a commit and reviewable.
8. Future capabilities should prefer controlled extension mechanisms over edits
   that destabilize the protected core.

## Recovery rule

If future work causes a regression:

`detect → isolate → preserve evidence → rollback/recover → test → verify → document`

The last verified release remains the recovery anchor until the new release
passes the same required gates.

## Release permanence

A release is not called immutable until:

- the exact source SHA is frozen;
- trusted CI has passed for that SHA;
- required migration/schema checks are recorded;
- the release manifest and SHA-256 are recorded;
- rollback/recovery evidence is retained;
- all applicable external production gates have attributable evidence;
- canonical references point to the same release;
- no unexplained branch/provenance divergence remains.

## Long-term operating principle

The system may evolve, but its core guarantees do not silently regress.
New features, providers, markets, AI capabilities, and integrations are
extensions of the durable foundation, not replacements for it.
