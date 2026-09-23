# Hussam NextGen — Yemen Platform System Alignment
## BUILD Phase 1 — Full-system Yemenization contract — 2026-09-24

### 1. Decision
Hussam is not being reduced to a simple Yemen marketplace.
The target is a Yemen-first unified operating platform in which every existing capability — Sovereign Core, Commerce/Marketplace, Finance, Inventory, Sales, Procurement, Payments, Logistics, Assets, Projects, CRM, Documents, Workflow, AI, HUS, Web/Android/API/POS — works naturally with Yemeni commercial reality while remaining reusable and extensible.
Yemenization is a cross-system compatibility layer, not a single checkout feature and not a fork of the application.

### 2. Without unnecessary restriction
The platform must not artificially force card-first checkout, mandatory online payment, one currency, one bank/wallet, one carrier, one geography model, one business model, always-online operation, or English-first terminology.
Real security, authorization, accounting integrity, idempotency, auditability, tenant isolation and external-provider requirements remain system integrity controls, not product restrictions.

### 3. Cross-system Yemenization matrix
| System | Yemen-ready behavior |
|---|---|
| Identity & Accounts | Arabic-first labels, configurable phone-oriented journeys, organizations, memberships, staff and delegated operators |
| Organizations | branches, departments, employees, owners, partners, delegated operation and multi-location support |
| Marketplace | multi-vendor commerce, local catalog/search, COD, transfer/payment choices, pickup/delivery, seller service areas |
| Commerce/Sales | cash, credit/receivable, partial payment, deposits, installments where configured, returns, exchanges, quotations and orders |
| Finance | YER and enabled currencies, market money-unit presentation, receivables/payables, cash/bank/wallet clearing, multi-branch accounting |
| Inventory | shops, warehouses, vans, branches, transfers, receiving, issuing, reservations and batch/serial/expiry where relevant |
| Procurement | local suppliers, purchase orders, receiving, supplier balances, partial settlement and multi-currency purchasing |
| Payments | COD, cash, manual transfer/reference, bank/wallet adapters, provider-neutral rails, reconciliation and settlement |
| Logistics | governorate/district/locality coverage, pickup, merchant delivery, third-party carriers, delivery zones and proof of delivery |
| Pricing | local currency display, wholesale/retail, branch pricing, customer groups, promotions and negotiated prices |
| Taxes/Fees | configurable rules rather than foreign hard-coding; scoped by market/tenant/transaction |
| CRM | phone-first customer records, locality, branches, sales history, support and follow-up |
| Documents | Arabic/English templates, local numbering, invoices, receipts, quotations and printable/digital formats |
| Notifications | SMS/WhatsApp/email/push adapters, retries and Arabic content |
| Search/Discovery | Arabic normalization, local aliases, locality/category search and low-bandwidth responses |
| Connectivity | cached safe reads, resumable workflows, idempotent writes and explicit pending/uncertain states |
| AI | Yemen-aware context, Arabic/local terminology and governed tool/action use |
| HUS | reusable workflows, Yemen market context, capability contracts and extension-safe execution |
| Analytics | branch/governorate/category/channel/currency-aware reporting |
| Admin | market configuration, provider capability, service areas, policies, audit and operations |
| Developer Platform | internal extension SDK, HUS modules, workflows, tools, UI schemas, adapters, tests and controlled release |
| Clients | responsive Web, Android-ready APIs, POS and integration surfaces with Arabic-first UX |

### 4. Money model
Separate currency identity, money-unit presentation, transaction currency, market/geography FX observations, accounting valuation and settlement currency.
No feature may invent an exchange rate or silently convert money.
Old/new YER presentation, where commercially necessary, is a presentation/configuration concern around the same currency identity unless an authoritative future requirement proves otherwise.

### 5. Commerce model
Support normal Yemeni transaction patterns: cash on delivery, cash at pickup, manual transfer/reference, bank/wallet payment through adapters, customer credit/receivable, deposits/advances, partial settlement, seller payout/settlement and refunds/returns.
Marketplace, Commerce and Finance remain separate authorities with shared contracts.

### 6. Geography model
Use one hierarchy: country → governorate → district → locality → address details.
Every location-aware service consumes the common geography/address context rather than inventing its own geography fields.
Coverage can differ by market, seller, branch, warehouse, delivery mode, provider and time window.

### 7. Connectivity model
Weak/intermittent connectivity is a normal operating condition. Use safe cached reads, local draft preservation, idempotency keys, retry only for retry-safe operations, explicit pending/sync states, conflict handling and resumable uploads where supported.

### 8. Local business flexibility
Support individual sellers, shops, multi-branch merchants, wholesalers/distributors, service businesses, clinics, dental laboratories, factories, project/contract operations, mosques/charitable projects, cooperatives/community operations, marketplace sellers and digital/service-only businesses.
These are configurations and verticals over shared engines, not copies of Finance, Inventory or Identity.

### 9. External integrations
Providers are integrations, not the platform. The architecture must permit adapters for wallets, banks/payment services, SMS, WhatsApp, email, maps/location, delivery/carriers, accounting import/export, identity providers, POS and other commerce channels.
No provider becomes a hard-coded sovereign-core dependency.

### 10. Definition of done
A system is Yemen-ready when its normal workflow works with Yemen market context; Arabic/local presentation is supported where user-facing; money and geography use shared primitives; local operational choices are configurable; weak connectivity does not create avoidable duplicate/false transactions; provider behavior is behind adapters; accounting invariants remain intact; auditability and tenant isolation remain intact; and the capability can be extended through the Developer Platform without cloning a core engine.

This is a product/architecture contract. It does not claim external provider certification or production readiness.