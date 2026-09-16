# AI-02 — Governed Commerce Intelligence Lock

Status: **ENGINEERING LOCK**

AI-02 adds a deterministic, domain-grounded intelligence layer over the locked Marketplace. It does not replace Marketplace authority and it does not execute mutations.

## Capabilities

- Customer commerce context scoped to the authenticated user.
- Public marketplace recommendations grounded only in published + approved listings.
- Seller operational intelligence for publication gaps, paused listings and zero-order signals.
- AI context envelopes where live Marketplace facts are authoritative and memory is contextual only.
- Proposal generation through the AI-01 runtime and approval boundary.

## Security rules

1. Every query is tenant/user/market scoped where applicable.
2. Customer recommendations cannot expose draft, rejected or unapproved listings.
3. Customer context can only read the authenticated buyer's orders.
4. AI-02 never writes Marketplace orders, listings, inventory, payments, payouts or accounting records.
5. A seller proposal creates an AI run/action only; mutation requires the existing approval and domain command boundaries.
6. No model provider is required for deterministic AI-02 correctness tests.
7. Live domain records outrank memory and external content is never treated as instructions.

## Control Center

AI-02 exposes governed endpoints suitable for the future Control Center. Configuration may tune an existing capability; new capability remains an engineering change.

## Release gate

AI-02 is locked only when the full test suite, migration upgrade/downgrade/re-upgrade, compile validation and baseline audits pass.
