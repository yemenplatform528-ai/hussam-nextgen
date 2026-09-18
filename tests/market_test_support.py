from decimal import Decimal
import json
from app.core.models.market import MarketContext, MarketCurrency, ProviderRegistryEntry, ProviderMarketCapability
from app.core.models.marketplace import MarketplaceFeeRule


def ensure_market(db, code='YE', currency='YER'):
    market=MarketContext(code=code,country_code=code,name='Test Market',locale='ar-YE',timezone='Asia/Aden',default_currency=currency,status='active')
    db.add(market); db.flush()
    db.add(MarketCurrency(market_id=market.id,currency=currency,is_default=True))
    db.add(MarketplaceFeeRule(market_id=market.id,name='Test configured fee',scope='global',commission_bps=250,fixed_fee=Decimal('0'),currency=currency,active=True))
    evidence = json.dumps({
        'identity_licensing': True, 'capability': True, 'market_currency_scope': True,
        'commercial_basis': True, 'technical_interface': True, 'authentication': True,
        'webhook_semantics': True, 'idempotency': True, 'settlement_reconciliation': True,
        'certification': True, 'operational_owner': True,
    }, sort_keys=True)
    provider = ProviderRegistryEntry(code='test-provider', organization_name='Test Provider', provider_type='payment', product_name='Test Pay', status='production', integration_mode='api', metadata_json=evidence)
    db.add(provider); db.flush()
    for capability in ('payment', 'refund', 'payout'):
        db.add(ProviderMarketCapability(provider_id=provider.id, market_id=market.id, capability=capability, rail='', currency=currency, active=True))
    db.commit()
    return market
