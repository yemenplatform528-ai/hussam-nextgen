# BUILD Phase 1 — Yemenization Market Findings
## Research baseline — 2026-09-24

**Status:** RESEARCH_ONLY / NON-BLOCKING  
**Certification boundary:** G01–G10 remain external and must close before production Yemenization implementation.

## Purpose
This document records current Yemen-market observations that can shape BUILD Phase 1 without changing the certified application core.

## Current market signals

### 1. Multi-vendor marketplaces are already familiar
Current Yemeni marketplace products describe multi-store discovery, seller participation, delivery, direct buyer/seller communication, classifieds, or broad category coverage.

Observed examples:
- Talabya describes a marketplace connecting buyers with verified local stores and explicitly says it does not compete by selling its own products.
- Bazzarry describes a marketplace/store aggregation model with home delivery and cash-on-delivery.
- Wateen describes multiple local stores on one platform with delivery.
- Yemen Mazad describes classifieds across vehicles, property, electronics, fashion, home/garden and other categories.
- Souqmy describes a Yemeni marketplace with cart, customer dashboard, favorites, messaging, notifications and auctions.
- Jawhar describes a comprehensive Yemeni marketplace emphasizing local sellers, broad catalog coverage, local payment options and delivery.
- JooExpress combines Yemeni sellers with international sourcing and a Saudi transit/shipping model.

Sources:
- https://apps.apple.com/us/app/talabya-%D8%B7%D9%84%D8%A8%D9%8A%D8%A9/id6502952414
- https://apps.apple.com/ye/app/bazzarry-%D8%A8%D8%A7%D8%B2%D8%A7%D8%B1%D9%8A/id1631702675
- https://play.google.com/store/apps/details?id=com.wateen.zandstuch
- https://play.google.com/store/apps/details?hl=en_US&id=com.yemenmazad.www
- https://play.google.com/store/apps/details?hl=en&id=com.souqmy.store
- https://play.google.com/store/apps/details?id=com.jawher.jawher
- https://jooexpress.com/en/about

### 2. Cash-on-delivery and local payment flexibility remain important
Public marketplace descriptions continue to mention payment on delivery and/or local payment methods. This supports keeping Hussam's payment layer provider-neutral rather than binding checkout to a single provider.

**Engineering consequence:** the provider-neutral payment contract already present in Hussam should remain the core. Yemenization should add market/provider adapters and capability discovery, not rewrite the payment domain.

### 3. Locality must be a first-class market dimension
Current products position themselves around Yemen-wide access, local sellers, city/country discovery and local delivery. This supports the existing Hussam market-context model and governorate-aware logistics direction.

**Engineering consequence:** Phase 1 should expose locality progressively:
`country → governorate → district/city → locality → delivery zone`
without forcing users to enter a complex address before it is necessary.

### 4. The user experience should hide infrastructure complexity
The current market signal is not that Yemen needs more screens. Existing products emphasize simple shopping, one-place discovery, delivery and familiar payment choices.

**Phase 1 UX principle:**
- Ask only what is necessary.
- Default to local context where known.
- Show price + delivery + payment capability together.
- Keep provider names secondary to the user's task.
- Preserve COD where operationally available.
- Make unavailable delivery/payment options explicit instead of failing silently.

### 5. Regulation must remain a live boundary
The Central Bank of Yemen publishes current regulatory material including electronic-money/mobile-money instructions, electronic KYC guidance, financial-consumer protection material, licensed-bank information, licensed exchange/remittance-agent lists for 2026, and an electronic-payment decision.

Source:
- https://cby-ye.com/pages/14

**Engineering consequence:** provider onboarding and payment certification cannot be inferred from an app's public marketing page. Production activation requires actual eligibility, contracts/interfaces, credentials, settlement/reconciliation evidence and applicable regulatory review.

## Phase 1 architecture direction
Do not fork the sovereign core.

Add Yemenization as a controlled market layer around existing capabilities:
1. MarketContext
2. YemenGeography
3. CurrencyContext
4. PaymentCapability
5. DeliveryCapability
6. SellerLocalization
7. BuyerLocalization
8. LocalSearch/Discovery
9. ConnectivityAwareUX
10. Evidence/ProviderCertification

The existing Marketplace, AI and HUS control-plane behavior remains protected.

## Explicit non-goals
- No payment provider is marked certified from public web information.
- No production credentials are added.
- No national geography dataset is inserted from unreviewed sources.
- No production gate is closed by this research.
- No core accounting/payment/marketplace rewrite is authorized by this document.

## Next controlled research
Before implementation:
1. Build a source-backed Yemen provider capability matrix.
2. Establish authoritative geography sources and provenance.
3. Define YER currency/display rules and market-context boundaries.
4. Define delivery-zone primitives for governorate/city/locality.
5. Map connectivity-aware checkout/search behavior.
6. Convert only approved findings into Phase 1 implementation specifications after certification lock.
