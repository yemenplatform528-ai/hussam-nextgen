# Yemen Geography Acceptance Gate

**Status:** PENDING — no national dataset accepted or imported  
**Gate owner:** Hussam NextGen engineering evidence process  
**Scope:** `YE` market administrative geography only

## Purpose

This gate is the final evidence boundary between a public/reference Yemen
administrative dataset and production data in Hussam NextGen.

A dataset is not accepted because it is public, popular, bilingual, or because
its counts appear plausible. Acceptance requires evidence for the exact
artifact that will be imported.

## Acceptance record

The reviewed record must identify:

1. **Canonical publisher** — organization that publishes the artifact.
2. **Dataset/artifact name** — exact dataset and version/release where available.
3. **Canonical source URI** — stable publisher URL.
4. **License** — exact license or explicit terms of use/attribution.
5. **Retrieved-at** — UTC timestamp for the exact artifact.
6. **Artifact preservation** — unchanged copy retained for audit.
7. **Artifact SHA-256** — hash of the exact bytes supplied to the importer.
8. **Schema** — fields, identifier format, hierarchy levels, and encoding.
9. **Coverage** — country, governorates, districts, and any locality level actually present.
10. **Hierarchy validation** — every child resolves to the correct parent level.
11. **Identifier validation** — unique identifiers and stable parent references.
12. **Name validation** — source-provided English/Arabic names where available; no invented names.
13. **Independent cross-check** — comparison against a separate credible reference, with discrepancies recorded rather than silently reconciled.
14. **Transformation record** — every normalization step from source artifact to importer CSV.
15. **Decision** — `ACCEPTED`, `REJECTED`, or `PENDING`, with rationale.

## Acceptance rules

The decision can be `ACCEPTED` only when all of the following are true:

- the exact artifact is preserved and hashed;
- provenance and licensing are documented;
- the artifact passes the importer validation contract;
- the hierarchy is complete for the levels being admitted;
- identifiers are unique and parent-child references are valid;
- discrepancies found in the independent cross-check are explicitly resolved,
  documented as source differences, or accepted as known limitations;
- no boundary, locality, code, or name has been invented to fill a gap;
- the transformation from source to import artifact is reproducible;
- the acceptance record names the exact SHA-256 that production import will use.

## Current decision

**PENDING.**

No national Yemen geography artifact currently has an acceptance record that
satisfies all requirements above. In particular, the existence of an OCHA/HDX
COD framework does not by itself prove that a current Yemen artifact is
finalized for this project. OCHA describes administrative boundaries as a
foundational dataset and states that a preferred set of administrative
boundaries must be endorsed as the Common Operational Dataset for the dataset
to be considered complete. cite-source:turn0search12

Accordingly, Hussam NextGen does **not** import a guessed 22-governorate,
335-district list, nor does it treat a public repository as the canonical
boundary source without completing this gate.

## Production mutation rule

The importer remains fail-closed. `--apply` is permitted only after the
acceptance record exists and the SHA-256 supplied to the importer exactly
matches the preserved reviewed artifact.

The database must never become the place where an unresolved source decision
is made.

## Evidence status vocabulary

- `CANDIDATE` — public source identified; not approved.
- `REVIEWED` — source/provenance/licensing examined; acceptance not complete.
- `ACCEPTED` — all gate requirements satisfied for the exact artifact hash.
- `REJECTED` — source fails one or more mandatory requirements.
- `PENDING` — evidence remains incomplete or a source decision is unresolved.

## Next executable step

Acquire/preserve one exact candidate artifact, create its acceptance record,
compute SHA-256, run the importer in dry-run mode, and perform the independent
cross-check. Do not run `--apply` until the decision is explicitly `ACCEPTED`.
