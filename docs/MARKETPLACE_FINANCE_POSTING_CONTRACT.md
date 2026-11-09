# Marketplace Finance Posting Contract

## Status

**PROPOSED — ENGINEERING DESIGN ONLY — FINANCE OWNER APPROVAL REQUIRED**

This contract is the implementation boundary for connecting Marketplace seller balances, COD remittance, payouts, refunds, and recovery to the existing authoritative Finance ledger. It does not approve any real cash custody, bank movement, account mapping, payout, refund, or production release.

## 1. Authorities and non-negotiable boundaries

1. The Finance journal is the authoritative General Ledger.
2. `MarketplaceSellerBalanceEntry` is an operational seller subledger. Its internal conservation checks do not prove General Ledger reconciliation.
3. Payment providers and carrier integrations supply evidence; neither may write directly to the authoritative Finance journal.
4. All journal postings must pass through the existing Finance posting authority. No direct SQL writes to journal tables.
5. A COD seller attestation is not carrier verification, cash receipt, remittance, or settlement.
6. Never manufacture a `PaymentSettlement`, provider payment reference, or electronic `PaymentRefund` to represent a cash COD event.
7. Posted journals are immutable. Corrections use linked reversal journals and compensating subledger entries.
8. Missing account mapping, missing evidence, unresolved reconciliation exceptions, closed fiscal periods, or invalid tenant/currency scope must fail closed.

## 2. Required event-to-ledger contract

| Business event | Required evidence | Required ledger/subledger outcome | Release condition |
|---|---|---|---|
| Verified electronic payment settlement | Provider identity, exact amount/currency, verified provider settlement reference, matched reconciliation run | Finance payment clearing/cash posting and verified-settlement evidence. This event is only one prerequisite for seller allocation; it must not independently create a second seller-payable credit. | Reconciliation is matched with zero exceptions |
| Order completion and seller allocation (electronic payments only) | Immutable order, market, seller, item totals, approved commission/tax calculation, and the same order's verified zero-exception electronic settlement | Exactly one seller subledger credit and corresponding Finance journal allocation, linked to one stable order-allocation idempotency identity | Both order completion and matched payment settlement exist. Whichever prerequisite arrives last may invoke the single idempotent allocation; the other event records evidence only. COD orders are excluded and use the COD remittance gate below. |
| COD collection | Carrier-signed event or platform-verified agent receipt; shipment binding; exact amount/currency; event identity and time | Logistics evidence record only. No seller subledger credit, seller payable, or Finance settlement is created at collection time. | Collection evidence verified |
| COD cash remittance | Collection evidence plus named cash custodian, receipt/bank reference, exact amount/currency, timestamp, and independent verifier | COD clearing/cash-in-transit movement through Finance. Seller subledger allocation is a separate, single idempotent action and may occur only after the remittance is reconciled and the approved business policy permits it. | Remittance evidence is accepted; reconciliation is matched with zero exceptions; required owner policy is approved |
| Seller payout | Verified seller destination, provider/cash disbursement reference, amount/currency, approval and completion evidence | Seller-payable subledger debit linked to Finance payout journal | Funds are disbursed and the linked journal is posted |
| Refund request/approval | Order/return/dispute authority, amount cap, reason, approver, maker/checker separation | No completed-refund status at request/approval time | Disbursement remains pending |
| Cash refund completion | Verified recipient, disbursement reference, amount/currency, proof of receipt, independent checker | Cash/bank journal plus linked seller/customer balance recovery entries | Disbursement and journal are both verified |
| Reversal/recovery | Original journal and subledger references, reason, authorized actor | New reversal journal and compensating subledger entry; original remains immutable | Reversal is balanced, linked, and audited |

## 3. Account mapping and posting validation

No account codes or account identifiers are prescribed by this document.

Before Marketplace posts to Finance, the implementation must resolve approved account roles for each tenant, market, currency, and event type. The mapping must be effective-dated and versioned. Candidate roles include payment clearing, receivable, seller payable, platform commission, COD cash-in-transit/clearing, cash/bank, payout clearing, and refund/recovery accounts; Finance ownership determines the actual accounts and accounting treatment.

The posting boundary must validate, at minimum:

- Account exists in the tenant-scoped chart of accounts.
- Account is active on the journal posting date.
- Account tenant matches the transaction tenant.
- Account currency is compatible with the journal currency.
- Account type is permitted for the configured posting role.
- Debit/credit lines balance and the fiscal period is open.
- Journal reference and source event are idempotent and unique.
- The account mapping version and approver are retained in the audit trail.

The current `post_journal` path does not yet enforce all chart-of-accounts properties at posting time. Do not treat a successful balanced journal as proof that its account mapping is valid until this validation boundary is implemented and tested.

## 4. Subledger-to-General-Ledger linkage

Every Marketplace seller-balance mutation that represents a financial event must have a durable link to the corresponding Finance journal and journal lines. The linkage must preserve one stable source-event identity and enforce uniqueness so retries, event reordering, and concurrent workers cannot create duplicate allocations. For electronic orders, completion and reconciled settlement are two prerequisites for one seller-allocation command, not two posting triggers. For COD orders, shipment completion and seller attestation never trigger seller allocation; only accepted and reconciled remittance can satisfy that gate. The linkage must preserve:

- Tenant, market, seller, order, payout/refund, currency, and source event identity.
- Seller-balance entry ID and Finance journal ID/reference.
- Posting role, mapping version, posting timestamp, and actor/service identity.
- Idempotency key and source-evidence hash.
- Reversal or recovery linkage where applicable.

Legacy seller-balance entries without a Finance journal must not be silently backfilled with invented accounting. Reconcile historical exposure and create any opening-balance or migration journals only under an approved Finance-owner procedure.

## 5. COD evidence and custody model

The COD workflow must distinguish these states:

1. `seller_attested` — seller-entered reference; not independently verified.
2. `carrier_verified` — signed carrier event or independently authenticated carrier/agent receipt.
3. `cash_received` — named custodian confirms physical cash handoff with receipt evidence.
4. `remitted` — cash deposited/transferred to the approved destination account.
5. `reconciled` — remittance matched to an independent cash/bank statement with zero exceptions.
6. `seller_allocated` — approved seller-payable allocation is posted and linked to Finance.

A later state must never be inferred from an earlier state. In particular, seller attestation must never unlock seller payout or cash refund.

**Current implementation boundary (2026-11-09):** the persisted `ShipmentCollection` model currently supports only `evidence_source='seller_attestation'` with `independently_verified=false`. The carrier/agent-verified states above are target states, not currently writable states; enabling them requires a future evidence-verification workflow, proof/actor provenance, and an explicit schema change.

**Evidence-storage dependency:** the current repository has no transaction-level receipt/file upload and secure evidence-storage adapter. The production `evidence/external` directory is for release-gate evidence and must not be repurposed as customer/courier receipt storage. A verified manual-agent workflow requires an approved private evidence store, immutable artifact references/hashes, access control, retention/deletion policy, and audited verifier identity before the source can be marked independently verified.

## 6. Reconciliation

The existing provider-statement reconciliation contract must not be misused to represent a COD cash remittance as an electronic provider payment. Extend the shared reconciliation authority with an explicit source type if appropriate, or introduce a COD remittance reconciliation adapter that produces the same deterministic classifications and exception-closure guarantees.

A reconciliation run may close only when its source identity/hash is stable, every expected reference is explicit, all amount/currency comparisons match, and exception count is zero. Reconciliation imports classify evidence; they do not themselves move money or post journals.

## 7. Refund and payout controls

- Preserve maker/checker separation for cash receipt, refund approval, and disbursement confirmation.
- A request or approval is not a completed refund.
- Partial refunds must reduce exposure exactly; full refunds must reverse held/eligible payout exposure.
- Paid payouts are never silently rewritten; use an explicit recovery workflow and journal.
- A seller payout cannot be released on the basis of shipment delivery or seller COD attestation alone.
- External provider/cash disbursement must be confirmed before marking a payout paid.
- All external actions require idempotency, audit provenance, and a recoverable exception state.

## 8. Recommended implementation sequence

1. Add chart-of-accounts validation and approved account-mapping configuration without seeding invented account codes.
2. Add one idempotent Finance journal ↔ seller-subledger allocation command for electronic orders; require both completed order and matched verified settlement, regardless of event order, and link payout separately.
3. Add tenant/market/currency reconciliation between seller subledger and Finance control accounts.
4. Add carrier/agent verification and separate COD cash-custody/remittance records.
5. Add COD remittance reconciliation; only a matched, zero-exception remittance plus approved business policy may trigger the single COD seller-allocation/payout path.
6. Add cash refund request/approval/disbursement/reconciliation as a separate cash workflow.
7. Run migration, replay/idempotency, reversal, cross-tenant, currency, fiscal-period, and failure-injection tests.
8. Obtain independent Finance review and external evidence before closing G04 or changing release status.

## 9. Decisions that remain external to engineering

| Decision | Required owner |
|---|---|
| Whether COD cash is held by the platform or remitted directly to the seller | Business/operations owner |
| Approved chart-of-accounts mapping and commission/tax treatment | Finance owner / qualified accountant |
| Carrier/agent evidence source and contractual acceptance | Logistics/business owner |
| Cashbox/bank custody and dual-control authority | Finance/operations owner |
| Permitted cash-refund channels, recipient verification, and limits | Finance + legal/compliance owner |
| Jurisdiction-specific COD disclosures and retention rules | Legal/compliance owner |

### Recommended default (not adopted)

Prefer centralized, documented cash custody with independent remittance reconciliation before seller payout; require two-person control for cash receipt and cash refunds; support carrier-signed evidence where available and a separately labeled platform-verified manual agent receipt where it is not. This recommendation is not authorization to change cash ownership, business terms, or accounting treatment.

## 10. Release boundary

This contract is not production certification. COD financial closure remains blocked until account mappings are approved and enforced, seller-subledger/General-Ledger linkage is implemented, COD remittance is independently verified and reconciled, cash refunds are auditable, and the required external Finance/legal/operations evidence is recorded.
