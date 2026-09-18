from sqlalchemy import select, create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
import pytest

from app.core.models.market import MarketContext, MarketCurrency
from app.engines.marketplace import MarketplaceService, MarketplaceError


def make_db():
    engine=create_engine("sqlite+pysqlite:///:memory:", future=True)
    @event.listens_for(engine, "connect")
    def _fk_on(conn, _): conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)()

def test_marketplace_does_not_autocreate_yemen_market(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'dev')
    db=make_db()
    with pytest.raises(MarketplaceError, match='market context is required'):
        MarketplaceService(db)._market_id()
    assert db.scalars(select(MarketContext)).all() == []


def test_explicit_active_market_is_required():
    db=make_db()
    market = MarketContext(code='YE', country_code='YE', name='Yemen', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    db.add(market); db.flush()
    db.add(MarketCurrency(market_id=market.id, currency='YER', is_default=True))
    db.commit()
    assert MarketplaceService(db)._market_id() == market.id
