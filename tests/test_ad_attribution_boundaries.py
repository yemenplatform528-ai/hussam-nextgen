from decimal import Decimal
import pytest
from sqlalchemy import select

from app.core.models.marketplace import MarketplaceListing, MarketplaceOrder, MarketplaceOrderLine
from app.core.models.marketplace_growth import MarketplaceAdCampaign
from app.engines.identity import IdentityService
from app.engines.marketplace_completion import MarketplaceCompletionService, MarketplaceCompletionError
from tests.test_marketplace_completion_core import setup


def test_ad_attribution_rejects_cross_tenant_references_and_uses_order_total():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db)
    ids=IdentityService(db)
    other_seller=ids.create_tenant('Other Seller')
    other_user=ids.create_user('other-seller-user','other-seller@example.test')
    ids.add_membership(other_user.id,other_seller.id,'owner')
    other_listing=MarketplaceListing(
        market_id=l.market_id,seller_tenant_id=other_seller.id,product_id=l.product_id,sku_id=l.sku_id,
        offer_id=None,item_id=l.item_id,warehouse_id=l.warehouse_id,category_id=l.category_id,
        slug='other-listing',title='Other Listing',description='',listing_type='product',
        currency='YER',unit_price=100,status='draft',stock_policy='managed',moderation_status='pending'
    )
    db.add(other_listing)
    other_order=MarketplaceOrder(reference='other-order',buyer_user_id=buyer.id,seller_tenant_id=other_seller.id,currency='YER',subtotal=500,shipping_fee=0,platform_fee=0,total=500,status='completed')
    db.add(other_order); db.commit(); db.refresh(other_listing); db.refresh(other_order)
    campaign=MarketplaceAdCampaign(seller_tenant_id=seller.id,name='AT',kind='sponsored_products',status='active',budget_daily=Decimal('20'))
    db.add(campaign); db.commit(); db.refresh(campaign)
    with pytest.raises(MarketplaceCompletionError, match='listing not found for seller'):
        svc.ad_event(seller.id,campaign.id,'click',listing_id=other_listing.id,currency='YER',bid=Decimal('1'))
    with pytest.raises(MarketplaceCompletionError, match='order not found for seller'):
        svc.attribute_ad_conversion(seller.id,campaign.id,other_order.id,Decimal('1'),listing_id=None)
    own_order=MarketplaceOrder(reference='own-order',buyer_user_id=buyer.id,seller_tenant_id=seller.id,currency='YER',subtotal=1000,shipping_fee=100,platform_fee=50,total=1150,status='completed')
    db.add(own_order); db.commit(); db.refresh(own_order)
    db.add(MarketplaceOrderLine(marketplace_order_id=own_order.id, listing_id=l.id, title_snapshot=l.title, quantity=1, unit_price=1150, line_total=1150))
    db.commit()
    attribution=svc.attribute_ad_conversion(seller.id,campaign.id,own_order.id,Decimal('1'),listing_id=l.id)
    assert attribution.attributed_revenue == Decimal('1150.0000')
