# Amazon Public Capability Scope Matrix

This is a clean-room functional benchmark. It targets publicly observable Amazon marketplace/seller-network capabilities, not private Amazon source code or internal architecture.

| # | Public capability family | Hussam authority | Status |
|---:|---|---|---|
| 1 | Catalog / product identity | Catalog | CLOSED |
| 2 | Listings / offers | Marketplace + Catalog | CLOSED |
| 3 | Featured Offer | Marketplace | CLOSED |
| 4 | Pricing automation | Marketplace pricing | CLOSED |
| 5 | Promotions | Marketplace Growth | CLOSED |
| 6 | Coupons | Marketplace Completion | CLOSED |
| 7 | B2B commerce | Marketplace Growth | CLOSED |
| 8 | Bundles | Commerce | CLOSED |
| 9 | Subscriptions | Commerce | CLOSED |
| 10 | Orders / multi-seller order | Commerce | CLOSED |
| 11 | Payments orchestration | Payments | CLOSED |
| 12 | Fees / settlement / payout | Finance | CLOSED |
| 13 | Returns / partial refunds | Commerce + Payments | CLOSED |
| 14 | Seller Center | Marketplace | CLOSED |
| 15 | Seller account health | Trust | CLOSED |
| 16 | Customer service | Trust / Service | CLOSED |
| 17 | Inventory / reservations | Inventory | CLOSED |
| 18 | Warehouses / transfers | Inventory | CLOSED |
| 19 | Fulfillment | Logistics | CLOSED |
| 20 | Pickup / service areas | Logistics | CLOSED |
| 21 | Advertising | Growth | CLOSED |
| 22 | Brands / Stores | Growth | CLOSED |
| 23 | Analytics | Analytics | CLOSED |
| 24 | Reports | Platform | CLOSED |
| 25 | Notifications | Platform | CLOSED |
| 26 | Feeds / bulk operations | Platform | CLOSED |
| 27 | Webhooks / integrations | Platform | CLOSED |
| 28 | Customer search / discovery | Marketplace | CLOSED |
| 29 | AI governed execution | Intelligence | CLOSED |
| 30 | HUS governed execution | Intelligence | CLOSED |

## Secondary public tools mapped into the families

Amazon also publicly exposes Product Opportunity Explorer, Growth Opportunities, Manage Your Experiments, A+ Content, Brand Analytics, Amazon Attribution, Brand Metrics, Brand Referral Bonus, Transparency, Currency Converter, Global Selling, Seller University, and related seller tools. These are treated as capabilities layered on the benchmark families above rather than as separate sovereign transaction authorities. Their functional domains map to Growth, Analytics, Brand, Catalog, Platform Integration, and Marketplace operations.

## Scope boundary

The benchmark is deliberately **Amazon marketplace/seller-network scope**. It does not claim equivalence to unrelated Amazon businesses such as AWS, Prime Video, Amazon Music, Kindle, or Amazon's private corporate/internal systems. Those are outside Hussam's agreed product boundary.
