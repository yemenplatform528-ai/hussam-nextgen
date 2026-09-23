# Hussam NextGen — Yemenization Phase 1 Product Contract
## 2026-09-24

Status: BUILD PREPARATION / PRODUCT CONTRACT

This document converts the approved Yemenization direction into an implementation contract without changing the certified core.

## Product identity

Hussam is a Yemen-first commerce platform.

Primary product:
- multi-store marketplace
- buyer experience
- seller/store experience
- catalog and inventory
- cart and checkout
- orders and order lifecycle
- local delivery and pickup
- cash on delivery
- optional local transfer/wallet methods
- Yemen-aware currency display
- Yemen-aware geography and locality
- local search and discovery
- connectivity-aware UX
- AI and HUS remain platform capabilities

## Experience principles

1. Commerce first: the user should be able to browse, order and receive without unnecessary setup.
2. Local by default: governorate, city, district and locality are first-class commerce context.
3. Payment choice: COD is a normal checkout path; other local methods are optional choices.
4. External payment systems remain integrations. Hussam does not need to recreate a wallet or financial network.
5. Currency display is a commerce concern: show the amount and currency context clearly and never invent an exchange rate.
6. Delivery is part of the order experience, not a separate product the buyer must understand.
7. Low-bandwidth resilience is a UX requirement.
8. Seller onboarding should be practical and commerce-oriented.
9. Marketplace, AI and HUS remain reusable core capabilities; Yemenization is an adapter/localization layer.
10. No hard-coded provider dependency.

## Phase 1 capability map

### Buyer
- browse without unnecessary friction
- locality-aware discovery
- product search
- seller/store discovery
- cart
- checkout
- COD
- optional transfer/wallet payment
- delivery address
- order tracking
- notifications

### Seller
- store profile
- product management
- inventory
- pricing
- availability
- delivery areas
- accepted payment options
- order acceptance
- order status
- sales view

### Delivery
- service areas
- pickup/delivery modes
- locality-aware fees
- order handoff states
- COD collection state
- return/cancellation states

### Money presentation
- YER display context
- USD/SAR where a seller or market context requires them
- explicit currency on every displayed amount
- exchange-rate source/context when conversion is shown
- no hard-coded national rate
- no automatic conversion unless a source/context exists

### Locality
Country -> Governorate -> District -> Locality/Area

The existing Y2 geography foundation remains the source model. National geography data is admitted only through the existing controlled ingestion process.

### Connectivity-aware UX
- lightweight first render
- avoid unnecessary blocking calls
- preserve checkout/order draft locally where safe
- retry transient network operations
- make sync state visible
- do not silently duplicate orders
- prioritize essential commerce actions over secondary media

## Payment model

Hussam represents payment as an order capability and state, not as a replacement for external payment infrastructure.

Supported Phase 1 concepts:
- cash on delivery
- manual transfer/reference
- optional external wallet/provider adapter
- payment pending
- payment confirmed
- payment failed
- refund/return state where the commerce flow requires it

Provider activation is configuration/integration work. A provider is never considered active merely because public marketing material exists.

## What Phase 1 does not require

- rebuilding the core marketplace
- a separate Yemen runtime fork
- a new financial subsystem
- a wallet inside Hussam
- a new national payment network
- mandatory electronic payment for buyers
- hard-coded provider logic
- hard-coded FX values
- imported geography data without provenance
- blocking the commerce experience on an external integration

## Implementation order

P1 — Yemen commerce context and geography admission
P2 — currency and amount presentation
P3 — delivery/service-area primitives
P4 — payment-option and COD UX
P5 — buyer/seller localization
P6 — connectivity-aware UX
P7 — integrated Yemen marketplace release candidate

Each step must reuse the existing core models and preserve the certification boundary.

## Definition of done for Phase 1

A buyer can discover a local product, understand the seller and location, place an order, choose COD or an available payment option, provide a practical delivery location, and follow the order lifecycle with minimal friction.

A seller can create/manage a store, publish products, define service areas and accepted payment choices, receive orders, and manage fulfillment.

The platform remains provider-neutral, geography-aware, currency-explicit, and resilient to intermittent connectivity.

## Control rule

This contract authorizes product/architecture preparation. It does not claim production certification, provider certification, or closure of G01-G10.
