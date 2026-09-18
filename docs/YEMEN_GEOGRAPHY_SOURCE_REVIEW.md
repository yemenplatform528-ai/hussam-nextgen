# Yemen Geography Source Review

**Status:** REVIEWED — NO NATIONAL DATASET IMPORTED
**Date:** 2026-09-18

## Decision

The production layer will use a provenance-first source gate for Yemen administrative geography. No dataset is promoted into the `YE` market merely because it is publicly available.

### Primary candidate: OCHA COD-AB

OCHA describes COD-AB as the common operational administrative-boundary dataset family, with administrative hierarchy, feature names and P-codes. Its published quality criteria include complete metadata, unique P-codes, correct nesting/topology, and country coverage. OCHA also states that COD-AB datasets are reviewed periodically.

For Yemen, a 2024 OCHA HDX COD-AB distribution is independently surfaced as containing 22 governorates and 335 districts, attributed to the Central Statistical Organization, with CC BY-IGO 3.0 licensing in the catalog source reviewed during this checkpoint.

**Important:** the catalog evidence is not itself the exact reviewed artifact. Therefore it is a source candidate, not an import authorization.

### Secondary candidate: Open Admin Data

`open-admin-data/yemen-administrative-divisions` publishes a bilingual dataset under CC-BY-4.0 and currently reports 22 governorates and 335 districts. It is useful as an independent cross-check, especially for names, counts and structural consistency.

It is not treated as the canonical production source because its provenance is different from the OCHA/COD-AB chain.

## Required promotion gate

Before any national geography is applied to production, the exact artifact must be:

1. downloaded from its canonical publisher;
2. stored unchanged as the reviewed artifact;
3. checked for license/attribution requirements;
4. checked for publication/update date and source metadata;
5. validated against the platform hierarchy contract;
6. validated for unique codes and parent-child integrity;
7. compared against an independent reference where practical;
8. hashed with SHA-256;
9. imported only with the exact reviewed hash supplied to `yemen_geography_import.py`.

The importer already fails closed when provenance or the exact artifact hash is missing or mismatched.

## Explicit non-decisions

- No national Yemen geography is currently considered imported.
- No claim is made that OCHA's current Yemen dataset is the legally authoritative national boundary definition.
- No coordinates, villages, localities, or extra administrative levels are invented from secondary sources.
- A public dataset's existence does not constitute platform approval.

## Reference standards reviewed

- OCHA COD-AB documentation and quality criteria.
- OCHA P-code guidance.
- OCHA COD-AB specification/validator documentation.
- Open Admin Data Yemen dataset metadata.

## Next engineering action

Acquire the exact OCHA Yemen COD-AB artifact, preserve it unchanged, run the production importer validator in dry-run mode, and produce a machine-readable review report before any database apply operation.
