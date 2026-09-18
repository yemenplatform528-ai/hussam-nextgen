# Yemen Payment Provider Certification Matrix

**Status:** engineering evidence register — not provider certification
**Updated:** 2026-09-18

This matrix separates **publicly documented capability** from **integration certification**. A provider is never marked `certified` merely because its website documents a product or payment capability.

## Acceptance states

- `discovered`: provider/product is identified.
- `public_capability_evidence`: an official or regulator source documents the capability.
- `contract_required`: commercial/integration agreement is still required.
- `api_pending`: technical interface/specification is not verified.
- `testing`: sandbox/production certification is in progress.
- `certified`: Hussam has verified the integration against an agreed contract and test evidence.
- `production`: certified integration is approved for production use.

## Current evidence matrix

| Provider / product | Type | Publicly documented capability | Evidence source | Hussam integration status | What is still missing |
|---|---|---|---|---|---|
| Al-Kuraimi / Kuraimi Jawal | bank/digital channel | transfers, deposits, bill payment, e-commerce/Haseb, YER/USD/SAR account transfers | Official Kuraimi pages | `public_capability_evidence` | API/merchant contract, technical spec, credentials, webhook/reconciliation certification |
| Al-Kuraimi / Haseb | merchant/e-commerce payment | merchant and domestic e-commerce payment is explicitly documented | Official Kuraimi Haseb page | `public_capability_evidence` | merchant onboarding/API or approved integration path, callback/webhook contract, settlement evidence |
| Al-Qutaibi / Qutaibi Mobile | bank/digital channel | payment, transfer, account management, e-commerce, FX buy/sell, bill payment | Official Qutaibi pages | `public_capability_evidence` | API/merchant contract, technical spec, credentials, webhook/reconciliation certification |
| Al-Qutaibi / Shalan (Shln) | wallet | official site documents an electronic wallet offered by the bank | Official Qutaibi homepage | `public_capability_evidence` | wallet API/spec, merchant acceptance contract, settlement/reconciliation evidence |
| Yemen Payments & Clearing Company (YPCC) | payment infrastructure | Central Bank reports establishment and infrastructure role | Central Bank of Yemen | `discovered` | Hussam participation/connection model, technical interface, eligibility, certification |
| Al-Najm | financial/remittance provider | **not yet accepted into the canonical provider registry from a sufficiently verified primary source in this pass** | — | `discovered` | primary official source + licensing/evidence + integration path |

## Regulatory gate

The Central Bank of Yemen's payment-service instructions state that the Central Bank maintains an updated list of licensed payment service providers and payment-system operators/managers, including suspended or cancelled licenses. Hussam therefore treats licensing as a separate evidence field and never infers it from a provider's marketing page.

The Central Bank has also publicly warned against dealing with unlicensed electronic-payment entities and wallets.

## Integration rule

A provider can enter the Hussam catalog before technical integration, but the provider **cannot be represented as an active production rail** until all of the following are present:

1. identity and legal/licensing evidence;
2. product/capability evidence;
3. market and currency scope;
4. commercial/contractual basis where required;
5. technical interface or approved operating procedure;
6. authentication/credential mechanism;
7. webhook/callback semantics when applicable;
8. idempotency and duplicate-event handling;
9. settlement and reconciliation evidence;
10. sandbox or controlled production certification;
11. operational owner and incident path.

## Evidence references

- Central Bank of Yemen: payment-service licensing instructions.
- Central Bank of Yemen: June 17, 2026 statement on the unified network and integration of banks and financial-service providers.
- Central Bank of Yemen: August 4, 2026 statement on establishment of the Yemen Payments & Clearing Company.
- Al-Kuraimi official documentation for Kuraimi Jawal, Haseb, payment and domestic transfers.
- Al-Qutaibi official documentation for Qutaibi Mobile, cards, SoftPOS and Shalan wallet.

**Important:** public web evidence documents capabilities; it does not prove that Hussam has an API contract, credentials, sandbox access, production approval, or settlement certification with any provider.
