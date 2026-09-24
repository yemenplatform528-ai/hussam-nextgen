from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.engines.marketplace_completion import MarketplaceCompletionService, MarketplaceCompletionError
from app.core.models.amazon_completion import *
from app.core.models.platform_completion import MarketplacePriceDecision
from app.core.models.marketplace_growth import MarketplaceAdCampaign, MarketplaceCustomerCase, MarketplaceBundle, MarketplaceSubscriptionOffer, MarketplaceBrand, MarketplaceBrandStore
from app.core.models.marketplace import MarketplaceOrder
from app.core.models.marketplace_growth import MarketplaceReportJob, MarketplaceNotification
from app.core.models.marketplace_growth import MarketplaceIntegrationApp


def setup():
    from tests.test_marketplace_completion_core import setup as s
    return s()


def test_competitive_repricing_is_audited_and_guardrailed():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db)
    from app.core.models.marketplace_growth import MarketplacePricingRule
    r=MarketplacePricingRule(seller_tenant_id=seller.id,name='guard',scope_json={'listing_id':l.id},action_json={'type':'floor'},min_price=Decimal('900'),max_price=Decimal('1100'),priority=1); db.add(r); db.commit(); db.refresh(r)
    svc.record_price_competitor(seller.id,l.id,'external',Decimal('800'),'YER')
    out=svc.reprice_against_market(seller.id,l.id,r.id)
    assert out['price']=='900.0000'
    assert db.scalar(select(MarketplacePriceDecision).where(MarketplacePriceDecision.id==out['decision_id'])).source=='competitive'


def test_health_enforcement_and_appeal_lifecycle():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    from app.core.models.marketplace import MarketplaceOrder
    for i in range(5):
        db.add(MarketplaceOrder(reference=f'h-{i}',buyer_user_id=buyer.id,seller_tenant_id=seller.id,currency='YER',subtotal=100,shipping_fee=0,platform_fee=0,total=100,status='cancelled',created_at=now))
    db.commit(); out=svc.enforce_health(seller.id,now-timedelta(minutes=1),now+timedelta(minutes=1)); assert out['status']=='restricted'
    appeal=svc.submit_appeal(seller.id,out['enforcement_id'],'inventory outage',{'ticket':'X'}); assert appeal.status=='submitted'
    resolved=svc.resolve_appeal(seller.id,appeal.id,True,'verified'); assert resolved.status=='approved'
    assert db.get(MarketplaceSellerEnforcement,out['enforcement_id']).status=='lifted'


def test_case_sla_escalation_and_shipment_events():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    case=MarketplaceCustomerCase(buyer_user_id=buyer.id,seller_tenant_id=seller.id,case_type='order',subject='Help',description='x'); db.add(case); db.commit(); db.refresh(case)
    sla=svc.open_case_sla(case.id,now+timedelta(hours=1),su.id); svc.escalate_case(case.id); assert sla.escalation_level==1
    order=MarketplaceOrder(reference='ship-1',buyer_user_id=buyer.id,seller_tenant_id=seller.id,currency='YER',subtotal=100,shipping_fee=0,platform_fee=0,total=100); db.add(order); db.commit(); db.refresh(order)
    sh=svc.create_shipment(seller.id,order.id,'carrier-x','TRK-1',now+timedelta(days=2)); ev=svc.record_shipment_event(seller.id,sh.id,'in_transit',now,{'city':'Aden'}); assert ev.event_code=='in_transit'


def test_integration_scope_rate_limit_and_report_notification_execution():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    app=MarketplaceIntegrationApp(owner_tenant_id=seller.id,name='App',client_id='scope-client',scopes_json=['orders.read'],rate_limit_per_minute=1); db.add(app); db.commit(); db.refresh(app)
    cred=svc.issue_integration_credential(seller.id,app.id,su.id,['orders.read'],'hash-1'); assert cred.id
    svc.consume_rate_limit(app.id,'2026-09-13T12:00');
    with pytest.raises(MarketplaceCompletionError): svc.consume_rate_limit(app.id,'2026-09-13T12:00')
    job=MarketplaceReportJob(tenant_id=seller.id,report_type='sales'); db.add(job); db.commit(); db.refresh(job); run=svc.run_report(seller.id,job.id,{'orders':1}); assert run.status=='completed'
    n=MarketplaceNotification(tenant_id=seller.id,notification_type='test',title='T',body='B'); db.add(n); db.commit(); db.refresh(n); d=svc.deliver_notification(seller.id,n.id,'in_app'); assert d.status=='delivered'


def test_b2b_bundle_subscription_brand_bulk_and_search_primitives():
    db,seller,buyer,su,l=setup(); svc=MarketplaceCompletionService(db); now=datetime.now(timezone.utc)
    q=svc.request_b2b_quote(seller.id,buyer.id,l.id,10,'YER',Decimal('900'),now+timedelta(days=2)); assert q.status=='requested'
    bundle=MarketplaceBundle(seller_tenant_id=seller.id,name='Kit',sku='KIT1',price=900,currency='YER',status='published',components_json=[{'sku':'rice','qty':1}]); db.add(bundle); db.commit(); db.refresh(bundle); order=MarketplaceOrder(reference='bundle-order',buyer_user_id=buyer.id,seller_tenant_id=seller.id,currency='YER',subtotal=900,shipping_fee=0,platform_fee=0,total=900); db.add(order); db.commit(); db.refresh(order); br=svc.reserve_bundle(seller.id,bundle.id,order.id,1); assert br.status=='reserved'
    offer=MarketplaceSubscriptionOffer(seller_tenant_id=seller.id,listing_id=l.id,interval_unit='month',interval_count=1,discount_bps=500); db.add(offer); db.commit(); db.refresh(offer); sub=svc.schedule_subscription(seller.id,offer.id,buyer.id,now+timedelta(days=30)); assert sub.status=='active'
    brand=MarketplaceBrand(owner_tenant_id=seller.id,name='Brand',slug='brand-x',status='verified'); db.add(brand); db.commit(); db.refresh(brand); store=MarketplaceBrandStore(brand_id=brand.id,slug='brand-store-x',title='Store'); db.add(store); db.commit(); db.refresh(store); published=svc.publish_brand_store(seller.id,store.id); assert published.status=='published'
    from app.core.models.platform_completion import MarketplaceFeedJob
    feed=svc.create_feed(seller.id,'catalog',{}); issues=svc.validate_bulk_rows(seller.id,feed.id,[{'row_number':2,'required_missing':['sku','price']}]); assert len(issues)==2
    ev=svc.record_analytics_event(seller.id,'purchase',900,str(order.id),{'channel':'search'}); assert ev.event_type=='purchase'
    se=svc.record_search_event(buyer.id,'rice',1,l.id); assert se.clicked_listing_id==l.id


def test_case_message_rejects_other_seller_case():
    db, seller, buyer, su, l = setup(); svc = MarketplaceCompletionService(db)
    other_tenant = __import__('app.engines.identity', fromlist=['IdentityService']).IdentityService(db).create_tenant('Other Seller')
    case = MarketplaceCustomerCase(buyer_user_id=buyer.id, seller_tenant_id=other_tenant.id, case_type='order', subject='Private', description='x')
    db.add(case); db.commit(); db.refresh(case)
    with pytest.raises(MarketplaceCompletionError, match='does not belong to seller'):
        svc.add_case_message(case.id, su.id, 'seller', 'no access', seller_tenant_id=seller.id)


def test_webhook_queue_rejects_other_seller_integration_app():
    db, seller, buyer, su, l = setup(); svc = MarketplaceCompletionService(db)
    other_tenant = __import__('app.engines.identity', fromlist=['IdentityService']).IdentityService(db).create_tenant('Other Seller')
    app = MarketplaceIntegrationApp(owner_tenant_id=other_tenant.id, name='Other App', client_id='other-scope-client', scopes_json=['orders.read'])
    db.add(app); db.commit(); db.refresh(app)
    with pytest.raises(MarketplaceCompletionError, match='does not belong to seller'):
        svc.queue_webhook(app.id, 'ORDER_CHANGE', 'evt-cross-tenant', {'order_id': 1}, owner_tenant_id=seller.id)


def test_completion_reference_ownership_rejects_cross_tenant_rule_and_bundle_order():
    db, seller, buyer, su, l = setup(); svc = MarketplaceCompletionService(db)
    from app.engines.identity import IdentityService
    from app.core.models.marketplace_growth import MarketplacePricingRule
    ids = IdentityService(db)
    other = ids.create_tenant('Other Seller')
    other_rule = MarketplacePricingRule(seller_tenant_id=other.id, name='other-rule', scope_json={}, action_json={'type':'floor'}, min_price=Decimal('1'), priority=1)
    db.add(other_rule)
    other_bundle = MarketplaceBundle(seller_tenant_id=other.id, name='Other Kit', sku='OTHER-KIT', price=100, currency='YER', status='published', components_json=[])
    db.add(other_bundle)
    other_order = MarketplaceOrder(reference='other-bundle-order', buyer_user_id=buyer.id, seller_tenant_id=other.id, currency='YER', subtotal=100, shipping_fee=0, platform_fee=0, total=100)
    db.add(other_order); db.commit(); db.refresh(other_rule); db.refresh(other_bundle); db.refresh(other_order)
    svc.record_price_competitor(seller.id, l.id, 'external', Decimal('80'), 'YER')
    out = svc.reprice_against_market(seller.id, l.id, other_rule.id)
    assert out['price'] == '80.0000'
    with pytest.raises(MarketplaceCompletionError, match='order not found for seller'):
        svc.reserve_bundle(seller.id, other_bundle.id, other_order.id, 1)
