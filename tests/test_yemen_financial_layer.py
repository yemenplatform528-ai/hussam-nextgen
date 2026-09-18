from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import MarketContext, MarketGeography, MarketMoneyUnit, MarketExchangeRate


def db():
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    @event.listens_for(engine, 'connect')
    def _fk_on(conn, _): conn.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)()


def market(s):
    m = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    s.add(m); s.flush(); return m


def test_money_units_can_distinguish_variants_without_changing_iso_currency():
    s=db(); m=market(s)
    s.add_all([
        MarketMoneyUnit(market_id=m.id, code='YER-CURRENT', currency='YER', variant='current', name='Yemeni rial current'),
        MarketMoneyUnit(market_id=m.id, code='YER-LEGACY', currency='YER', variant='legacy', name='Yemeni rial legacy'),
    ])
    s.commit()
    assert {x.variant for x in s.scalars(select(MarketMoneyUnit)).all()} == {'current','legacy'}


def test_fx_can_be_market_scoped_or_geography_scoped():
    s=db(); m=market(s)
    root=MarketGeography(market_id=m.id, code='YE', level='country', name='Yemen'); s.add(root); s.flush()
    gov=MarketGeography(market_id=m.id, parent_id=root.id, code='YE-ADN', level='governorate', name='Aden'); s.add(gov); s.flush()
    s.add_all([
        MarketExchangeRate(market_id=m.id, base_currency='USD', quote_currency='YER', rate=Decimal('1600'), source_type='official', source_reference='reviewed-source', effective_at=datetime.now(timezone.utc)),
        MarketExchangeRate(market_id=m.id, geography_id=gov.id, base_currency='USD', quote_currency='YER', rate=Decimal('1601.25'), source_type='market_observed', source_reference='reviewed-market-observation', effective_at=datetime.now(timezone.utc)),
    ])
    s.commit()
    rows=s.scalars(select(MarketExchangeRate)).all()
    assert len(rows)==2 and any(x.geography_id == gov.id for x in rows)


def test_fx_rejects_nonpositive_and_same_currency():
    s=db(); m=market(s)
    now=datetime.now(timezone.utc)
    with pytest.raises(Exception):
        s.add(MarketExchangeRate(market_id=m.id, base_currency='USD', quote_currency='YER', rate=0, source_type='official', source_reference='x', effective_at=now)); s.commit()
    s.rollback()
    with pytest.raises(Exception):
        s.add(MarketExchangeRate(market_id=m.id, base_currency='YER', quote_currency='YER', rate=1, source_type='official', source_reference='x', effective_at=now)); s.commit()
