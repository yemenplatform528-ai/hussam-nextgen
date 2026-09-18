from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.models import MarketplaceListing
from app.core.models.platform_completion import MarketplacePriceDecision, MarketplaceCouponRedemption, MarketplaceAdCharge, MarketplaceSellerHealthSnapshot, MarketplaceFeedJob, MarketplaceWebhookDelivery
from app.core.models.marketplace_growth import MarketplaceAdCampaign, MarketplaceIntegrationApp
from app.engines.marketplace_completion import MarketplaceCompletionService, MarketplaceCompletionError


def setup():
    from tests.test_marketplace import setup as base_setup
    db,seller,buyer_t,buyer,seller_user=base_setup()
    from app.engines.marketplace import MarketplaceService, ListingInput
    m=MarketplaceService(db)
    m.register_seller(seller.id,'complete-seller','Complete Seller')
    m.review_seller_verification(seller.id,seller_user.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh'))
    m.moderate_listing(l.id,seller_user.id,'approved'); m.publish_listing(seller.id,l.id)
    return db,seller,buyer,seller_user,l


def test_pricing_decision_is_server_authoritative():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace_growth import MarketplacePricingRule
    db.add(MarketplacePricingRule(seller_tenant_id=seller.id,name='floor',scope_json={'listing_id':l.id},action_json={'type':'floor'},min_price=Decimal('1200'),priority=1)); db.commit()
    out=svc.evaluate_price(seller.id,l.id)
    assert out['price']=='1200.0000'
    assert db.scalar(select(MarketplacePriceDecision).where(MarketplacePriceDecision.listing_id==l.id)).proposed_price==Decimal('1200.0000')


def test_coupon_limits_and_discount():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    c=svc.create_coupon(seller.id,'SAVE10','percentage',Decimal('10'),now-timedelta(minutes=1),now+timedelta(hours=1),currency='YER',minimum_subtotal=500,per_buyer_limit=1)
    o=svc.redeem_coupon(buyer.id,1,'SAVE10',Decimal('1000'),'YER')
    assert o['discount']=='100.0000'
    with pytest.raises(MarketplaceCompletionError): svc.redeem_coupon(buyer.id,2,'SAVE10',Decimal('1000'),'YER')


def test_cpc_charge_and_budget_are_audited():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db)
    c=MarketplaceAdCampaign(seller_tenant_id=seller.id,name='SP',kind='sponsored_products',status='active',budget_daily=Decimal('20')); db.add(c); db.commit(); db.refresh(c)
    ev=svc.ad_event(seller.id,c.id,'click',listing_id=l.id,currency='YER',bid=Decimal('5'))
    assert ev['cost']=='5.0000'
    assert db.scalar(select(MarketplaceAdCharge).where(MarketplaceAdCharge.campaign_id==c.id)).amount==Decimal('5.0000')
    with pytest.raises(MarketplaceCompletionError): svc.ad_event(seller.id,c.id,'click',listing_id=l.id,currency='YER',bid=Decimal('20'))
    with pytest.raises(MarketplaceCompletionError, match='currency is required'):
        svc.ad_event(seller.id,c.id,'click',listing_id=l.id,bid=Decimal('1'))


def test_health_snapshot_and_integration_primitives():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    hs=svc.health_snapshot(seller.id,now-timedelta(days=1),now+timedelta(minutes=1))
    assert hs.order_count==0 and hs.status=='healthy'
    feed=svc.create_feed(seller.id,'PRODUCT_DATA',{'sku':'x'}); assert feed.status=='queued'
    done=svc.complete_feed(seller.id,feed.id,True); assert done.status=='completed'
    app=MarketplaceIntegrationApp(owner_tenant_id=seller.id,name='Connect',client_id='client-complete',webhook_url='https://example.invalid/hook'); db.add(app); db.commit(); db.refresh(app)
    wh=svc.queue_webhook(app.id,'ORDER_CHANGE','evt-1',{'order_id':1}); assert wh.status=='queued'
    assert db.scalar(select(MarketplaceWebhookDelivery).where(MarketplaceWebhookDelivery.id==wh.id)) is not None
