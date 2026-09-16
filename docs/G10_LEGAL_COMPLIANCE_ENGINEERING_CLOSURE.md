# G10 — Legal / Compliance — Engineering Readiness

## Scope
This document closes the **engineering readiness** work for Gate G10. It does **not** provide legal advice, legal interpretation, regulatory approval, or a declaration of compliance in any jurisdiction.

## Implemented controls
- Provider- and jurisdiction-neutral compliance contracts in `app/core/compliance.py`.
- Machine-checkable required policy catalog covering:
  - Terms of Service
  - Privacy Notice
  - Seller Terms
  - Marketplace Prohibited Goods
  - Returns, Refunds and Disputes
  - Payments and COD Disclosures
  - Intellectual Property Notice and Takedown
  - Data Retention Schedule
- Each policy template explicitly marks the boundary as **EXTERNAL LEGAL APPROVAL REQUIRED**.
- Compliance controls link each control area to the policy artifacts it depends on.
- The readiness harness validates completeness without accepting drafts as legal approval.
- No personal data, identity documents, credentials, provider secrets, or legal-client confidential material are required in the repository.

## Engineering policy boundary
The repository supplies the technical hooks and policy artifact structure. The final wording, jurisdictional applicability, retention periods, consumer rights, seller obligations, prohibited categories, tax/payment disclosures, dispute process, intellectual-property procedure, and required notices must be determined and approved externally by qualified counsel/compliance ownership for each launch jurisdiction.

## Required external review
At minimum, the external G10 review must determine and document:
1. Applicable launch jurisdiction(s) and responsible legal entity.
2. Consumer/e-commerce terms and mandatory disclosures.
3. Privacy/data-protection basis, notices, retention and deletion obligations.
4. Seller onboarding, prohibited goods, verification and suspension rules.
5. Returns, refunds, complaints and dispute/consumer-protection requirements.
6. Payment, COD, settlement, fee and tax disclosures.
7. Intellectual-property notice/takedown and repeat-infringer handling where applicable.
8. Record-keeping, audit, lawful-request and incident-notification obligations where applicable.
9. Marketplace content/moderation responsibilities and escalation ownership.
10. Final approval of the exact public policy artifacts and release scope.

## Readiness command
```text
python scripts/compliance_readiness.py --output /tmp/hussam-g10-compliance-readiness.json
```

The command must report `COMPLIANCE_READINESS_OK`, but that result only means the engineering policy pack is structurally complete. It is **not** legal approval.

## External evidence required for CLOSED
- Approved policy artifacts for the actual launch jurisdiction(s).
- Named legal/compliance owner or organization, without placing personal secrets in the repository.
- Written review/approval decision and date.
- Evidence that the approved policy versions match the release scope.
- Evidence of required public disclosure/consent/notice flows where applicable.
- Any required regulator, marketplace, payment, consumer-protection, privacy or contractual approvals applicable to the launch.
- External evidence envelope using the `legal_compliance.*` prefix and SHA-256 as required by `docs/PRODUCTION_EVIDENCE_PROTOCOL.md`.

**Status: ENGINEERING_READY / PENDING_EXTERNAL**
