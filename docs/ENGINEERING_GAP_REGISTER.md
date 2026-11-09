# Hussam NextGen — Engineering Gap Register

## Purpose

This register distinguishes remaining engineering work from external
certification work. It prevents production blockers from being confused with
feature gaps and prevents external evidence from being fabricated.

## Findings

| Area | Finding | Classification | Required before product engineering continues? |
|---|---|---|---|
| G01–G10 | Engineering closures are complete | Closed engineering | No |
| Production certification | 10 external gates still require real evidence | External | No |
| Amazon public scope | Internal pre-certification audit reports 30/30 capability families represented | Engineering scope | No |
| Yemenization Phase 1 | Runtime activation, checkout context, payment gates, seller context, COD/payment UX, delivery/coverage wiring and connectivity-safe buyer flow are implemented and CI-verified | Closed engineering phase | No |
| Production identity | Real OIDC provider registration and browser flow not certified | External | No, until launch |
| Production data | Real PostgreSQL migration/restore not certified | External | No, until launch |
| Payments | Real provider rails/webhooks/reconciliation not certified | External | No, until launch |
| Logistics | Real carrier integration not certified | External | No, until launch |
| Browser/mobile | Real deployed-device E2E not certified | External | No, until launch |
| Security | External security assessment not performed | External | No, until launch |
| DR/observability | Real restore/RPO/RTO and alert delivery not certified | External | No, until launch |
| Operations | Real operational drill/reviewer evidence not certified | External | No, until launch |
| Legal | External legal approval not obtained | External | No, until launch |

## Decision

No blocking engineering defect was identified by the current repository-level
closure audits. The remaining launch-critical items are external certification
or the later Yemenization phase.

The next work should therefore deepen product capability only when it creates a
clear user-facing value or closes a verified engineering gap; it should not
reopen the G01–G10 foundation without evidence of regression.


## 2026-09-27 status synchronization

Yemenization Phase 1 engineering is **CLOSED** at the repository level. The runtime activation boundary, Yemen checkout context, authoritative payment gate, seller context propagation, shipping/delivery UX, and desktop/mobile browser contract are merged into `main` and covered by green CI. This does **not** certify real payment providers, carriers, production identity, production restore, external security assessment, operations, or legal approval; those remain G01–G10 external gates.


## 2026-11-09 — COD settlement and refund closure correction

The previous Phase 1 closure statement must be read as a closure of the Yemen runtime/checkout integration slice, **not** as proof that the full COD money lifecycle is complete.

### Verified implementation boundary

- Checkout records the selected payment_method_code on the customer and seller orders. COD orders do not receive an electronic payment_reference merely by being created.
- LogisticsProductionService.create_cod_collection accepts a collection reference only after the shipment is delivered and requires the exact shipment COD amount and currency. It creates a ShipmentCollection and an outbox event.
- That ShipmentCollection is evidence that the carrier/fulfillment collection step was recorded. It does not itself prove remittance to Hussam, settlement into a seller balance, a Finance journal, or reconciliation.
- MarketplaceService.settle_order_payment requires an actual PaymentSettlement, a matching payment reference, provider identity, exact amount/currency/market, and closed reconciliation. The current COD order path does not create that electronic payment reference or a COD-specific remittance settlement.
- Marketplace payout eligibility remains settlement-reference gated. A delivered/collected COD order must not be treated as a paid-out or financially settled seller balance.
- MarketplaceService.approve_refund requires an order payment reference and delegates to PaymentProductionService.create_refund. That path does not support a COD cash refund. The seller return UI now fails closed for COD at the refund stage instead of offering an electronic refund action.

### Classification

| Gap | Classification | Current behavior | Required closure |
|---|---|---|---|
| COD collection-to-remittance | Verified engineering gap | Shipment collection receipt can be recorded; no COD remittance/reconciliation path is established | Carrier/agent handoff, remittance receipt, exact amount/currency, idempotency, Finance journal, reconciliation, and audit linkage |
| COD seller payout | Verified engineering gap | Electronic settlement path requires PaymentSettlement; COD payout remains held unless a valid settlement reference exists | COD-specific settlement contract that proves remittance and posts/reconciles through the authoritative Finance ledger before payout eligibility |
| COD cash refund | Verified engineering gap | Return can be reviewed/received/inspected, but electronic refund approval is blocked without a payment reference | Controlled cash/transfer refund disbursement record, source account/cashbox, journal posting, recipient evidence, exact amount/currency, reversal and audit controls |

### Non-negotiable controls

1. Delivery is not payment settlement.
2. A courier collection receipt is not proof that the collected cash reached Hussam or the seller.
3. A COD order must not receive a synthetic electronic payment reference to bypass settlement checks.
4. A COD refund must not be marked refunded without a real disbursement record and Finance evidence.
5. Seller payout eligibility must remain blocked until remittance and reconciliation are verified.
6. The implementation must extend the existing Logistics, Marketplace, Payments and Finance authorities; it must not introduce a parallel ledger.

### Decision

COD remains a valid buyer checkout method and shipment collection can be recorded, but **COD financial closure (remittance → ledger → reconciliation → seller payout) and COD cash refunds are not yet launch-complete**. These are explicit engineering work items, not provider certification claims. No synthetic settlement, journal, or refund was created to conceal the gap.


## 2026-11-09 — COD collection evidence authenticity correction

A source-level review of the current COD collection endpoint narrows the meaning of the collection record described above:

- `POST /marketplace/seller/fulfillments/{fulfillment_id}/cod-collection` is authenticated with `seller_guard`; the seller supplies a free-form collection reference, amount, and currency.
- The service verifies seller ownership of the fulfillment, existence of its shipment, delivered shipment state, exact COD amount/currency, and uniqueness/idempotency of the collection record.
- This route does **not** verify a carrier-signed webhook, authenticated carrier/agent identity, independent cash handoff evidence, or remittance custody. Therefore the resulting `ShipmentCollection(status='collected')` is currently a **seller-submitted collection attestation**, not independently verified carrier evidence.

### Additional verified engineering gap

| Gap | Classification | Current behavior | Required closure |
|---|---|---|---|
| COD collection authenticity and custody | Verified engineering gap | Seller can submit a collection reference after shipment delivery; no carrier signature/agent identity or independent custody evidence is validated | Accept a carrier-signed event or platform-verified agent receipt with tenant/shipment binding, external event identity, exact amount/currency, event-time validation, idempotency, custody handoff and audit provenance; preserve a separately labeled seller attestation when no carrier integration exists |

### Additional non-negotiable control

7. A seller-submitted COD collection attestation must never be presented as carrier-verified cash collection or remittance. UI, API responses, and finance decisions must preserve the evidence source and verification level.

The existing fail-closed settlement and refund controls remain correct and must not be weakened while this evidence gap is closed.


## 2026-11-09 — Marketplace seller subledger to General Ledger bridge

A source-level review of the current seller settlement and payout paths found an additional accounting boundary that must be closed before seller balances can be treated as fully reconciled financial liabilities:

- `MarketplaceService.settle_order_payment` validates a real `PaymentSettlement` and credits the `MarketplaceSellerBalanceEntry` subledger for an eligible completed order.
- `MarketplaceService.mark_payout_paid` validates the seller destination/provider gate and debits the same seller subledger when payout is marked paid.
- These marketplace paths do not call the Finance `post_journal` authority or create a journal-to-subledger linkage. The payment settlement journal records cash/clearing movement, but it does not by itself establish the seller-payable and payout postings.
- The Finance `post_journal` path now resolves every line to an existing account in the same tenant, locks account rows during posting, rejects inactive accounts for new journals, and enforces account currency when the account is currency-specific. Reversals may reuse an inactive account from the original journal so historical entries remain reversible. Event-specific account-type mapping (for example, approved clearing, cash, receivable, inventory, payable, commission, and seller-liability accounts) remains an owner-approved prerequisite; no account codes are seeded or invented.
- The seller subledger has its own conservation checks, but those checks do not prove General Ledger reconciliation.

### Additional verified engineering gap

| Gap | Classification | Current behavior | Required closure |
|---|---|---|---|
| Marketplace seller subledger ↔ General Ledger | Verified engineering gap | Seller settlement and payout mutate `MarketplaceSellerBalanceEntry` without linked Finance journal entries | Define approved account mappings by tenant/market/currency; post idempotent settlement, seller-payable, commission, payout, refund and recovery journals through the existing Finance authority; link subledger entries to journal references/lines; enforce account ownership/activity/currency, fiscal-period controls, reversals, reconciliation and audit provenance |

### Control

The marketplace seller balance remains an operational subledger, not a substitute for the authoritative Finance General Ledger. Do not claim accounting reconciliation or production payout certification from seller-balance conservation alone. Do not invent account codes or post journals until the account mapping and cash-custody policy are approved.


## 2026-11-09 — Transaction evidence storage prerequisite

A source-tree review found no transaction-level file upload or private evidence-storage adapter in the current application. No `UploadFile`, S3 client, presigned upload/download route, or transaction `EvidenceArtifact` model is present. The repository's `evidence/external` directory is reserved for release-gate evidence and must not be repurposed for customer, seller, or courier receipts.

| Gap | Classification | Current behavior | Required closure |
|---|---|---|---|
| Secure transaction evidence storage | Verified engineering gap | No application-level private upload/storage contract exists for COD receipts, carrier events, or cash-refund proof | Select an approved storage provider; implement private tenant-scoped objects, short-lived access, upload type/size validation, malware scanning where supported, immutable SHA-256 evidence hashes, actor/access audit, retention/deletion policy, and evidence-to-business-record linkage |

Until this is closed, a manually entered receipt reference remains an attestation and must not be upgraded to independently verified evidence. Storage provider, retention, privacy, and cost settings require owner/security approval before deployment.
