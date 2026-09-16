from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.persistence import Base
from app.core.models import (
    Tenant, User, TenantMembership, MarketplaceAddress,
    MarketContext, MarketCurrency, MarketGeography, MarketCoverage,
    ProviderRegistryEntry, ProviderMarketCapability, PaymentMethodCatalogEntry,
)


def db():
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    @event.listens_for(engine, 'connect')
    def _fk_on(dbapi_connection, _):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)()


def test_yemen_market_and_currency_foundation():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    s.add_all([
        MarketCurrency(market_id=m.id, currency='YER', is_default=True),
        MarketCurrency(market_id=m.id, currency='USD'),
        MarketCurrency(market_id=m.id, currency='SAR'),
        MarketCurrency(market_id=m.id, currency='AED'),
    ])
    s.commit()
    assert s.scalar(select(MarketContext).where(MarketContext.code == 'YE')).default_currency == 'YER'
    assert {x.currency for x in s.scalars(select(MarketCurrency)).all()} == {'YER','USD','SAR','AED'}


def test_geography_hierarchy_and_coverage():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    country = MarketGeography(market_id=m.id, code='YE', level='country', name='Yemen', name_ar='اليمن')
    s.add(country); s.flush()
    gov = MarketGeography(market_id=m.id, parent_id=country.id, code='YE-ADN', level='governorate', name='Aden', name_ar='عدن')
    district = MarketGeography(market_id=m.id, parent_id=gov.id, code='YE-ADN-MAN', level='district', name='Mansoura', name_ar='المنصورة')
    s.add(gov); s.flush(); district.parent_id = gov.id; s.add(district); s.flush()
    s.add(MarketCoverage(market_id=m.id, geography_id=gov.id, status='available'))
    s.commit()
    assert district.parent_id == gov.id
    assert s.scalar(select(MarketCoverage).where(MarketCoverage.geography_id == gov.id)).status == 'available'


def test_provider_registry_separates_provider_from_rail():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    p = ProviderRegistryEntry(code='example-wallet', organization_name='Example', provider_type='payment', product_name='Wallet', status='discovered', integration_mode='none')
    s.add_all([m,p]); s.flush()
    c = ProviderMarketCapability(provider_id=p.id, market_id=m.id, capability='merchant_payment', rail='wallet', currency='YER')
    s.add(c); s.commit()
    assert c.rail == 'wallet'
    assert p.status == 'discovered'


def test_payment_method_catalog_is_market_scoped():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    s.add_all([
        PaymentMethodCatalogEntry(market_id=m.id, code='wallet', name='Wallet', method_type='wallet'),
        PaymentMethodCatalogEntry(market_id=m.id, code='bank', name='Bank', method_type='bank'),
        PaymentMethodCatalogEntry(market_id=m.id, code='cash', name='Cash', method_type='cash', requires_provider=False),
        PaymentMethodCatalogEntry(market_id=m.id, code='cod', name='Cash on Delivery', method_type='cod', requires_provider=False),
    ])
    s.commit()
    assert {x.code for x in s.scalars(select(PaymentMethodCatalogEntry)).all()} == {'wallet','bank','cash','cod'}


def test_address_extension_preserves_legacy_fields():
    s = db()
    tenant = Tenant(name='T1', status='active')
    user = User(id='u1', email='u1@example.com', active=True)
    s.add_all([tenant,user]); s.flush()
    s.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, role='owner', active=True)); s.flush()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    country = MarketGeography(market_id=m.id, code='YE', level='country', name='Yemen', name_ar='اليمن')
    s.add(country); s.flush()
    gov = MarketGeography(market_id=m.id, parent_id=country.id, code='YE-ADN', level='governorate', name='Aden', name_ar='عدن')
    s.add(gov); s.flush()
    a = MarketplaceAddress(user_id=user.id, label='home', recipient_name='Buyer', phone='700000000', governorate='Aden', city='Aden', address_line='Main', landmark='Landmark', country_code='YE', market_id=m.id, governorate_id=gov.id, address_confidence='high', delivery_instructions='Call first')
    s.add(a); s.commit()
    x = s.get(MarketplaceAddress, a.id)
    assert x.governorate == 'Aden' and x.governorate_id == gov.id
    assert x.market_id == m.id and x.address_confidence == 'high'


def test_address_coordinates_are_checked():
    s = db()
    tenant = Tenant(name='T1', status='active'); user = User(id='u1', email='u1@example.com', active=True)
    s.add_all([tenant,user]); s.flush(); s.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, role='owner', active=True)); s.flush()
    with pytest.raises(Exception):
        s.add(MarketplaceAddress(user_id='u1', label='x', recipient_name='Buyer', phone='1', governorate='Aden', city='Aden', address_line='x', geo_lat=100, address_confidence='low'))
        s.commit()



def test_market_allows_only_one_default_currency():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    s.add(MarketCurrency(market_id=m.id, currency='YER', is_default=True)); s.flush()
    s.add(MarketCurrency(market_id=m.id, currency='USD', is_default=True))
    with pytest.raises(Exception):
        s.commit()


def test_geography_country_root_cannot_have_parent():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    s.add(MarketGeography(market_id=m.id, code='YE', level='country', name='Yemen', parent_id=999999))
    with pytest.raises(Exception):
        s.commit()


def test_non_country_geography_requires_parent():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush()
    s.add(MarketGeography(market_id=m.id, code='YE-ADN', level='governorate', name='Aden'))
    with pytest.raises(Exception):
        s.commit()


def test_geography_parent_must_belong_to_same_market():
    s = db()
    m1 = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    m2 = MarketContext(code='XX', country_code='XX', name='Other', locale='en-XX', timezone='UTC', default_currency='USD', status='active')
    s.add_all([m1, m2]); s.flush()
    root1 = MarketGeography(market_id=m1.id, code='YE', level='country', name='Yemen')
    root2 = MarketGeography(market_id=m2.id, code='XX', level='country', name='Other')
    s.add_all([root1, root2]); s.flush()
    s.add(MarketGeography(market_id=m2.id, parent_id=root1.id, code='XX-1', level='governorate', name='Wrong Market Parent'))
    with pytest.raises(Exception):
        s.commit()


def test_coverage_geography_must_belong_to_same_market():
    s = db()
    m1 = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    m2 = MarketContext(code='XX', country_code='XX', name='Other', locale='en-XX', timezone='UTC', default_currency='USD', status='active')
    s.add_all([m1, m2]); s.flush()
    root = MarketGeography(market_id=m1.id, code='YE', level='country', name='Yemen')
    s.add(root); s.flush()
    s.add(MarketCoverage(market_id=m2.id, geography_id=root.id, status='available'))
    with pytest.raises(Exception):
        s.commit()


def test_provider_wildcard_capability_is_explicit_and_unique():
    s = db()
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    p = ProviderRegistryEntry(code='provider', organization_name='Provider', provider_type='payment', product_name='Wallet')
    s.add_all([m, p]); s.flush()
    s.add(ProviderMarketCapability(provider_id=p.id, market_id=m.id, capability='merchant_payment', rail='', currency=''))
    s.flush()
    s.add(ProviderMarketCapability(provider_id=p.id, market_id=m.id, capability='merchant_payment', rail='', currency=''))
    with pytest.raises(Exception):
        s.commit()


def test_address_geography_must_match_address_market():
    s = db()
    tenant = Tenant(name='T1', status='active'); user = User(id='u2', email='u2@example.com', active=True)
    s.add_all([tenant, user]); s.flush()
    s.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, role='owner', active=True)); s.flush()
    m1 = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    m2 = MarketContext(code='XX', country_code='XX', name='Other', locale='en-XX', timezone='UTC', default_currency='USD', status='active')
    s.add_all([m1, m2]); s.flush()
    root1 = MarketGeography(market_id=m1.id, code='YE', level='country', name='Yemen')
    root2 = MarketGeography(market_id=m2.id, code='XX', level='country', name='Other')
    s.add_all([root1, root2]); s.flush()
    a = MarketplaceAddress(user_id=user.id, label='x', recipient_name='Buyer', phone='1', governorate='Other', city='Other', address_line='x', market_id=m1.id, governorate_id=root2.id)
    s.add(a)
    with pytest.raises(Exception):
        s.commit()
