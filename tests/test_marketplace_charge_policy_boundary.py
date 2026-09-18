from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.engines.marketplace import MarketplaceService, MarketplaceError
from app.core.models.marketplace import MarketplaceChargeRule
from tests.test_marketplace import setup

def test_no_charge_policy_means_zero_not_invented_tax():
    db,seller,*_=setup(); m=MarketplaceService(db)
    # setup creates a market/currency context used by the service
    rule, amount=m.marketplace_charge_preview(Decimal('1000'),'YER','tax')
    assert rule is None and amount == Decimal('0.0000')

def test_active_charge_policy_is_time_bounded_and_deterministic():
    db,seller,*_=setup(); m=MarketplaceService(db); now=datetime.now(timezone.utc)
    db.add(MarketplaceChargeRule(name='Documented charge',charge_type='tax',jurisdiction_code='TEST',rate_bps=150,fixed_amount=Decimal('2'),policy_version='test-v1',effective_from=now-timedelta(minutes=1),effective_to=now+timedelta(hours=1)))
    db.commit()
    rule, amount=m.marketplace_charge_preview(Decimal('1000'),'YER','tax',jurisdiction_code='TEST')
    assert rule.policy_version=='test-v1' and amount==Decimal('17.0000')

def test_expired_charge_policy_is_not_applied():
    db,seller,*_=setup(); m=MarketplaceService(db); now=datetime.now(timezone.utc)
    db.add(MarketplaceChargeRule(name='Expired',charge_type='tax',rate_bps=1000,policy_version='expired',effective_from=now-timedelta(hours=2),effective_to=now-timedelta(hours=1)))
    db.commit()
    rule, amount=m.marketplace_charge_preview(Decimal('1000'),'YER','tax')
    assert rule is None and amount==Decimal('0.0000')
