# Yemen Evidence Disposition

**Status:** REVIEWED — no external evidence promoted to production certification
**Review date:** 2026-09-19

## Purpose

This document is the current disposition checkpoint between the engineering readiness system and real external evidence. It records what can be treated as evidence, what remains only public capability information, and what is explicitly not accepted.

## 1. Administrative geography

**Disposition: `PENDING_REVIEW_ARTIFACT`**

No national Yemen administrative dataset is promoted into the canonical market dataset from public availability alone.

The project requires the exact preserved artifact, provenance, license/attribution, publication/update information, SHA-256, hierarchy validation, and an independent structural cross-check before database application. The importer remains fail-closed until those conditions are met.

The current OCHA COD-AB status information does not by itself establish a finalized Yemen artifact for this project. An independent public administrative-divisions dataset may be used as a cross-check, but is not automatically canonical.

### Independent geography cross-check update

A second independent public dataset was inspected directly from `YemenOpenSource/Yemen-info` (`main`, `yemen-info.json`, Git blob SHA `30c22263c57022bed8bf511c1b2f975164897bb1`). Complete JSON parsing returns 22 governorates and 335 districts. The repository itself cautions that its data are not guaranteed error-free and may become outdated, so this result is corroboration only. It strengthens the 22/335 structural finding but does not close the canonical-artifact gate.

## 2. Payment providers and payment infrastructure

**Disposition: `PUBLIC_CAPABILITY_ONLY` unless a provider-specific certification package exists.**

The current provider matrix correctly distinguishes documented provider capability from Hussam integration certification. No provider is promoted to `certified` or `production` merely because an official website or regulator page describes a payment product.

The Central Bank of Yemen states that the unified network is the primary channel for financial transfers and that banks and financial-service providers must complete required connectivity and integration. The Central Bank also describes YPCC as part of the national payments infrastructure modernization effort. These statements are regulatory/infrastructure evidence; they are not Hussam credentials, API access, contracts, sandbox results, or production certification.

## 3. Acceptance rule

An external evidence record may be accepted by the Hussam readiness system only when it has:

- exact source/artifact identity;
- source URI or canonical provenance;
- SHA-256 for the reviewed artifact where an artifact exists;
- retrieval date;
- reviewer reference;
- acceptance reference;
- license/attribution information where applicable;
- a documented review decision.

Acceptance of an evidence record does **not** automatically create geography, currency, FX, provider, rail, adapter, credentials, or production access.

## 4. Current Yemen activation posture

The engineering platform is prepared to evaluate readiness, but the national Yemen market must remain **`EVIDENCE_REQUIRED`** until the missing external evidence is actually acquired, reviewed, and accepted.

No national geography import, provider production certification, API credential, or live settlement integration is claimed by this checkpoint.

## 5. Next evidence actions

1. Preserve and review an exact Yemen geography artifact from a suitable canonical publisher when available.
2. Independently cross-check its governorate/district hierarchy.
3. Preserve licensing/provenance and compute the artifact SHA-256.
4. For each payment provider, obtain the actual integration package: legal/licensing basis, commercial basis, technical interface, authentication, webhook/idempotency semantics, settlement/reconciliation evidence, certification result, and operational owner.
5. Only then promote the corresponding readiness evidence record.

## Independent cross-check checkpoint

The earlier 335-vs-333 note has been refined. The current candidate publishes 22 governorates and 335 districts, and the OCHA/HDX `cod-ab-yem` metadata independently identifies the reviewed COD-AB v01 dataset as 22 governorates and 335 districts. Its XLSX metadata reports 336 `yem_admin2` rows (335 districts plus header) and 23 `yem_admin1` rows (22 governorates plus header), with P-codes. Older references that report 333 are therefore treated as historical/version-variant references rather than a sufficient basis to reject the 335-district candidate.

The evidence gate remains open for a different reason: Hussam has not yet preserved the exact OCHA resource bytes locally, computed their SHA-256, and performed a record-level P-code/parent comparison against the candidate. Until that exact artifact-level reconciliation is complete, no national geography is accepted or imported.

Reviewed: 2026-09-19
Disposition: PENDING_ARTIFACT_RECONCILIATION
