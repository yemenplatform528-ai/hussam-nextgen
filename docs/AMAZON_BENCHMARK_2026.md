# Amazon Public Benchmark — 2026 Working Reference

Hussam uses public Amazon documentation as a capability benchmark only. No
private Amazon source code, credentials, private datasets, or internal APIs are
copied.

## Benchmark observations

- Seller Central spans product/catalog work, inventory, orders, finance,
  customers, marketing and seller account health.
- Amazon's public SP-API onboarding shows an end-to-end seller workflow from
  catalog lookup and listing, through pricing, orders and fulfillment, with
  FBA/FBM alternatives. It also documents individual, batch and bulk access
  patterns and granular application roles.
- Amazon Business supports business prices, quantity discounts, bulk workflows,
  package hierarchies and B2B product discovery.
- Amazon Ads exposes Sponsored Products, Sponsored Brands and Display, with
  budgets, bids, targeting, reporting and moderation requirements.
- Amazon's public API documentation includes reports, notifications, feeds,
  listings, pricing, orders, shipping, fulfillment inbound/outbound, supply
  sources, transfers, invoices and related seller services.

## Design translation into Hussam

Hussam adopts the capability concepts but keeps a different authority model:

`Client -> API -> Identity/Policy -> Domain Service -> Engine -> Core Authority -> Persistence -> Audit/Event`

External integrations, advertising, AI and HUS cannot bypass payment, inventory,
identity, policy, audit or accounting authorities.

## Sources

- Amazon Seller Central: https://sell.amazon.com/tools/seller-central
- Amazon SP-API onboarding: https://developer-docs.amazon.com/sp-api/docs/onboarding-overview
- Amazon SP-API reference: https://developer-docs.amazon.com/sp-api
- Amazon Business: https://sell.amazon.com/programs/amazon-business
- Amazon B2B pricing: https://sell.amazon.com/blog/amazon-b2b-prices
- Amazon Ads sponsored ads: https://advertising.amazon.com/products/sponsored-ads
- Amazon Sponsored Products: https://advertising.amazon.com/solutions/products/sponsored-products
- Amazon Sponsored Brands: https://advertising.amazon.com/solutions/products/sponsored-brands
