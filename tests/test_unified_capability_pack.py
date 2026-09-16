from datetime import datetime, timezone, timedelta
from decimal import Decimal
from app.core.models.marketplace_growth import *

def test_capability_pack_models_can_persist():
    from tests.test_marketplace import setup
    session,*_=setup()
    seller=1
    # This test exercises metadata creation in the in-memory project fixture without
    # depending on authentication or a live external provider.
    objects=[
        MarketplacePricingRule(seller_tenant_id=seller,name='auto-price',scope_json={'sku':'*'},action_json={'type':'floor'},priority=10),
        MarketplacePromotion(seller_tenant_id=seller,name='Launch',kind='percentage_off',starts_at=datetime.now(timezone.utc),ends_at=datetime.now(timezone.utc)+timedelta(days=1)),
        MarketplaceBrand(owner_tenant_id=seller,name='Hussam Demo',slug='hussam-demo'),
        MarketplaceAdCampaign(seller_tenant_id=seller,name='Search',kind='sponsored_products'),
        MarketplaceB2BPrice(seller_tenant_id=seller,listing_id=1,currency='YER',unit_price=Decimal('100'),min_quantity=5),
        MarketplaceBundle(seller_tenant_id=seller,name='Starter',sku='B-1',price=Decimal('100'),currency='YER'),
        MarketplaceSubscriptionOffer(seller_tenant_id=seller,listing_id=1,interval_unit='month'),
        MarketplaceSellerHealthMetric(seller_tenant_id=seller,metric_code='order_defect_rate',value=Decimal('0'),period_start=datetime.now(timezone.utc),period_end=datetime.now(timezone.utc)),
        MarketplaceWarehouse(owner_tenant_id=seller,code='MAIN',name='Main'),
        MarketplacePickupPoint(operator_tenant_id=seller,code='P1',name='Pickup'),
        MarketplaceServiceArea(operator_tenant_id=seller,code='A1',name='Area'),
        MarketplaceReportJob(tenant_id=seller,report_type='sales'),
        MarketplaceNotification(tenant_id=seller,notification_type='order',title='Order'),
        MarketplaceIntegrationApp(owner_tenant_id=seller,name='Connect',client_id='client-demo'),
    ]
    session.add_all(objects); session.commit()
    assert session.query(MarketplacePricingRule).count()==1
    assert session.query(MarketplaceIntegrationApp).count()==1
