# Yemen Geography Source Review

**Status:** REVIEWED — NO NATIONAL DATASET IMPORTED  
**Date:** 2026-09-18

## Decision

Hussam NextGen uses a provenance-first source gate for Yemen administrative geography. Public availability alone never authorizes promotion into the `YE` market.

### Standards reference: OCHA COD-AB

OCHA defines COD-AB as the common operational administrative-boundary dataset family. Its documented quality criteria include metadata/source information, unique P-codes, complete parent identifiers, correct nesting/topology, and country coverage. OCHA also describes periodic review/update of COD-AB datasets. cite-source:turn0search2

The current OCHA COD-AB status dashboard, updated 12 September 2026, lists Yemen (`YEM`) with a 2026 HNRP context and a COD-AB work order in `Initialized` status. This means the current dashboard does **not** give us evidence to treat a newly updated Yemen COD-AB artifact as already finalized for this project. cite-source:turn0search11

### Independent cross-check: Open Admin Data

`open-admin-data/yemen-administrative-divisions` currently publishes bilingual administrative data and reports 22 governorates and 335 districts under CC-BY-4.0. It is useful as an independent structural/name cross-check, but it is not promoted to canonical source status merely because it is public. cite-source:turn0search0

#### Artifact-level finding (2026-09-19)

The candidate repository was inspected directly at commit `3eeb32f7811db7f4a91d1a86f64e01ccc60d22b6`. Its published structure reports 22 governorates and 335 districts; district records are supplied separately in `data/all-district.json`. The candidate therefore has a plausible current 335-district structure, but it is still not treated as the canonical source.

A stronger independent checkpoint is now available from the OCHA/HDX Yemen COD-AB metadata mirror. The current `cod-ab-yem` metadata identifies the source as the Central Statistical Organization (CSO), says OCHA Yemen contributed it, states that the dataset was reviewed for accuracy and completeness on 23 December 2024, and explicitly defines the dataset as 22 governorates and 335 districts. The metadata also identifies the XLSX resource as P-coded and reports 336 rows in the `yem_admin2` sheet (335 district records plus the header) and 23 rows in `yem_admin1` (22 governorate records plus the header).

This materially changes the interpretation of the earlier `335-vs-333` note: 333 is present in older/historical references, but 335 is directly corroborated by the reviewed OCHA/HDX COD-AB v01 metadata and by the current independent candidate. The discrepancy should therefore no longer be described as evidence that the candidate count is wrong. It remains a **provenance/artifact-acquisition gate**, because the exact OCHA resource bytes have not yet been preserved locally and SHA-256ed by Hussam, and a record-level P-code comparison against the candidate has not yet been executed.

### Independent structural cross-check: YemenOpenSource

A second independent public dataset was inspected directly from `YemenOpenSource/Yemen-info`, `main`, using the repository blob for `yemen-info.json` (Git blob SHA `30c22263c57022bed8bf511c1b2f975164897bb1`). Parsing the complete JSON yields **22 governorates and 335 districts**. Its repository documentation states that the project contains governorates, districts, uzaal and villages, while also warning that its information may become outdated and is not guaranteed to be error-free; therefore it is used only as an independent structural cross-check, not as the canonical source.

This gives Hussam two independent public structural corroborations of the 22/335 count: the current `open-admin-data/yemen-administrative-divisions` dataset and `YemenOpenSource/Yemen-info`. Neither substitutes for preservation and hashing of the exact canonical OCHA/HDX artifact.

## Promotion gate

Before any national geography is applied to production, the exact artifact must be:

1. obtained from its canonical publisher;
2. preserved unchanged;
3. checked for license/attribution requirements;
4. checked for publication/update date and source metadata;
5. normalized only through a documented transformation step;
6. validated against the Hussam hierarchy contract;
7. validated for unique codes and parent-child integrity;
8. compared against an independent reference where practical;
9. hashed with SHA-256;
10. applied only when the exact reviewed hash is supplied to `scripts/yemen_geography_import.py`.

The importer fails closed when required provenance is missing or when the supplied SHA-256 does not match the exact input artifact.

## Explicit non-decisions

- No national Yemen geography is currently imported.
- No claim is made that any public dataset is the legally authoritative Yemeni boundary definition.
- No coordinates, villages, localities, or extra administrative levels are invented.
- No current OCHA Yemen artifact is treated as approved merely because OCHA maintains the COD-AB framework.

## Next action

Acquire an exact, reviewable Yemen administrative artifact from a canonical publisher when available, preserve it unchanged, run dry-run validation, compare it against an independent reference, and produce an auditable acceptance report before any database apply.
