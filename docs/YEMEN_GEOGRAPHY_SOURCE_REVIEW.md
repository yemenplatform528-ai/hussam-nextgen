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

The repository's `data/all-flat.csv` at commit `3eeb32f7811db7f4a91d1a86f64e01ccc60d22b6` was inspected directly. Despite the filename, the retrieved CSV contains the 22 governorate records only; district records are published separately in `data/all-district.json`. The CSV schema also does not match Hussam's ingestion contract directly (`code,level,name,name_ar,parent_code,status,metadata_json`).

Therefore this specific CSV is **not accepted as the direct import artifact**. It may remain a cross-check/reference input, but any use in the canonical importer would require a documented, deterministic transformation and a newly hashed transformed artifact, followed by the normal hierarchy and independent-cross-check gates.

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
