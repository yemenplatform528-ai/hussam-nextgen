# Production Evidence Protocol

This protocol defines how Hussam converts engineering readiness into real production evidence.

## Non-negotiable rule

Configuration, unit tests, mocks, screenshots of configuration, or an arbitrary file are **not** enough to close a production gate.

A gate becomes `CLOSED` only when an evidence envelope is supplied and it:

1. identifies the exact gate;
2. identifies the real environment/source;
3. records the checks actually performed;
4. records a review decision and reviewer;
5. references an external evidence artifact;
6. contains the artifact's SHA-256; and
7. passes `scripts/production_evidence_protocol.py` validation.

The validator is deliberately fail-closed: missing envelopes, invalid JSON, non-PASS results, missing checks, missing artifacts, path traversal, or hash mismatch remain `PENDING_EXTERNAL`.

## Evidence lifecycle

`ENGINEERING_READY → CERTIFICATION_RUN → ARTIFACT_CAPTURED → HASH_RECORDED → REVIEWED → CLOSED`

A failed or missing external run remains `PENDING_EXTERNAL`.

## Envelope format

For gate `payments`, provide `payments.json` alongside the externally generated artifact:

```json
{
  "gate": "payments",
  "environment": "provider-sandbox",
  "source": "payment-provider-certification",
  "performed_at": "2026-09-13T00:00:00Z",
  "result": "PASS",
  "reviewed_by": "certification-owner",
  "checks": ["capture", "webhook-signature", "refund", "reconciliation"],
  "artifact": {
    "path": "payments.report.pdf",
    "sha256": "<64 lowercase hexadecimal characters>"
  }
}
```

Run:

```text
python scripts/production_evidence_protocol.py --evidence-dir <evidence-dir> --output <manifest.json>
```

The repository must never contain secrets, credentials, tokens, payment-card data, private identity documents, or raw provider secrets in evidence artifacts.

## Gate artifact prefixes

- `identity_oidc.*`
- `postgresql.*`
- `payments.*`
- `accounting.*`
- `logistics.*`
- `browser_mobile_e2e.*`
- `security.*`
- `backup_dr_observability.*`
- `operations.*`
- `legal_compliance.*`

The corresponding `.json` file is the required evidence envelope; it must reference a separate artifact.

## Yemenization boundary

Production evidence adapters are provider-neutral. Yemen-specific providers, currencies, address rules, COD, local carriers, and settlement rules are added later through the same adapter contracts and do not require replacing the Sovereign Core.
