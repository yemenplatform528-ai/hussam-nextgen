from decimal import Decimal
from app.core.models.market import MarketContext, MarketCurrency
from app.core.models.marketplace import MarketplaceFeeRule


def ensure_market(db, code='YE', currency='YER'):
    market=MarketContext(code=code,country_code=code,name='Test Market',locale='ar-YE',timezone='Asia/Aden',default_currency=currency,status='active')
    db.add(market); db.flush()
    db.add(MarketCurrency(market_id=market.id,currency=currency,is_default=True))
    db.add(MarketplaceFeeRule(market_id=market.id,name='Test configured fee',scope='global',commission_bps=250,fixed_fee=Decimal('0'),currency=currency,active=True))
    db.commit()
    return market
