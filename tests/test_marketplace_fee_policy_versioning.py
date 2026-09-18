from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from app.engines.marketplace import MarketplaceService
from app.core.models.marketplace import MarketplaceFeeRule, MarketplaceOrderFee
from tests.test_marketplace import setup


def test_fee_policy_window_and_snapshot_are_recorded():
    db,seller,buyer_t,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'policy-seller','Policy Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,__import__('app.engines.marketplace',fromlist=['ListingInput']).ListingInput('rice','Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id); m.add_to_cart(buyer.id,l.id,1)
    now=datetime.now(timezone.utc)
    rule=MarketplaceFeeRule(name='Versioned',scope='seller',seller_tenant_id=seller.id,commission_bps=800,fixed_fee=Decimal('5'),priority=1,active=True,policy_version='2026-09-v2',effective_from=now-timedelta(minutes=1),effective_to=now+timedelta(hours=1))
    db.add(rule); db.commit()
    order=m.checkout(buyer.id)[0]
    fee=db.scalar(select(MarketplaceOrderFee).where(MarketplaceOrderFee.marketplace_order_id==order.id))
    assert fee.policy_version=='2026-09-v2'
    assert fee.policy_snapshot['commission_bps']==800
    assert fee.policy_snapshot['fixed_fee']=='5.0000'


def test_expired_rule_is_not_selected():
    db,seller,buyer_t,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'expired-seller','Expired Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,__import__('app.engines.marketplace',fromlist=['ListingInput']).ListingInput('rice','Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id); m.add_to_cart(buyer.id,l.id,1)
    now=datetime.now(timezone.utc)
    db.add(MarketplaceFeeRule(name='Expired',scope='seller',seller_tenant_id=seller.id,commission_bps=900,active=True,policy_version='expired',effective_from=now-timedelta(hours=2),effective_to=now-timedelta(hours=1))); db.commit()
    order=m.checkout(buyer.id)[0]
    fee=db.scalar(select(MarketplaceOrderFee).where(MarketplaceOrderFee.marketplace_order_id==order.id))
    assert fee.commission_bps != 900
    assert fee.policy_version != 'expired'
