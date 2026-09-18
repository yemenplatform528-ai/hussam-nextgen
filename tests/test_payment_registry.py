import json
from app.core.models.market import MarketContext, ProviderRegistryEntry, ProviderMarketCapability, PaymentRailRegistryEntry, PaymentAdapterRegistryEntry
from app.engines.payment_adapters import REQUIRED_PRODUCTION_EVIDENCE
from app.engines.payment_registry import resolve_payment_adapter
from app.core.persistence import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _db():
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def _provider(db, market):
    evidence = json.dumps({k: True for k in REQUIRED_PRODUCTION_EVIDENCE})
    p = ProviderRegistryEntry(code='registry-provider', organization_name='Registry Provider', provider_type='payment', product_name='Demo', status='production', integration_mode='api', metadata_json=evidence)
    db.add(p); db.flush()
    db.add(ProviderMarketCapability(provider_id=p.id, market_id=market.id, capability='payment', rail='wallet', currency='YER', active=True))
    db.flush()
    return p


def test_resolver_requires_certified_rail_and_production_adapter():
    engine, factory = _db()
    with factory() as db:
        market = MarketContext(code='REG', country_code='YE', name='Registry Market', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
        db.add(market); db.flush(); p = _provider(db, market)
        rail = PaymentRailRegistryEntry(market_id=market.id, code='wallet', capability='payment', currency='YER', status='certified')
        db.add(rail); db.flush()
        db.add(PaymentAdapterRegistryEntry(provider_id=p.id, rail_id=rail.id, adapter_code='demo.wallet', adapter_version='1.0.0', status='production', active=True)); db.commit()
        r = resolve_payment_adapter(db, p.code, market.id, 'payment', 'wallet', 'YER')
        assert r.allowed and r.adapter_code == 'demo.wallet'
    engine.dispose()


def test_resolver_fails_closed_without_active_adapter():
    engine, factory = _db()
    with factory() as db:
        market = MarketContext(code='REG2', country_code='YE', name='Registry Market 2', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
        db.add(market); db.flush(); p = _provider(db, market)
        db.add(PaymentRailRegistryEntry(market_id=market.id, code='wallet', capability='payment', currency='YER', status='certified')); db.commit()
        r = resolve_payment_adapter(db, p.code, market.id, 'payment', 'wallet', 'YER')
        assert not r.allowed and 'production_adapter_not_active' in r.blocked_reasons
    engine.dispose()
