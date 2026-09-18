import pytest
from decimal import Decimal
from sqlalchemy import select
from app.engines.marketplace import MarketplaceService, ListingInput
from app.core.models.marketplace import MarketplaceFeeRule, MarketplaceOrderFee
from tests.test_marketplace import setup


def test_checkout_uses_server_fee_rule_and_audits_fee():
    db,seller,buyer_t,buyer,su=setup()
    m=MarketplaceService(db)
    m.register_seller(seller.id,'fee-seller','Fee Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,__import__('app.engines.marketplace',fromlist=['ListingInput']).ListingInput('rice','Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,1)
    rule=MarketplaceFeeRule(name='Seller Override',scope='seller',seller_tenant_id=seller.id,commission_bps=750,fixed_fee=Decimal('10'),priority=1,active=True)
    db.add(rule); db.commit()
    order=m.checkout(buyer.id)[0]
    assert order.platform_fee == Decimal('47.5000')
    fee=db.scalar(select(MarketplaceOrderFee).where(MarketplaceOrderFee.marketplace_order_id==order.id))
    assert fee is not None
    assert fee.commission_bps==750
    assert fee.fixed_fee==Decimal('10.0000')
    assert fee.amount==Decimal('47.5000')


def test_disabled_rules_fail_closed_after_configuration_exists():
    db,seller,buyer_t,buyer,su=setup()
    m=MarketplaceService(db)
    db.query(MarketplaceFeeRule).delete(); db.add(MarketplaceFeeRule(name='Disabled',scope='global',commission_bps=500,active=False)); db.commit()
    m.register_seller(seller.id,'fee-seller','Fee Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,__import__('app.engines.marketplace',fromlist=['ListingInput']).ListingInput('rice','Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,1)
    try:
        m.checkout(buyer.id)
        assert False, 'checkout should fail when configured fee rules are inactive'
    except ValueError as exc:
        assert 'fee rule' in str(exc)


def test_empty_fee_policy_fails_closed():
    db,seller,buyer_t,buyer,buyer_user=setup()
    m=MarketplaceService(db)
    db.query(MarketplaceFeeRule).delete(); db.commit()
    m.register_seller(seller.id,'fee-empty','Fee Empty'); m.review_seller_verification(seller.id,buyer_user.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice-empty','Rice Empty','', 'product','YER',Decimal('500'),'rice','wh'))
    m.moderate_listing(l.id,buyer_user.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,1)
    with pytest.raises(ValueError, match='fee rule'):
        m.checkout(buyer.id)
