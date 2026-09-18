from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.market import MarketContext, MarketCurrency
from app.core.models.marketplace import MarketplaceFeeRule
from app.engines.identity import IdentityService
from app.engines.marketplace import MarketplaceService, MarketplaceError


def test_checkout_rejects_client_supplied_platform_fee():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ids=IdentityService(db); buyer_t=ids.create_tenant('Buyer'); buyer=ids.create_user('buyer','buyer@example.com'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    market=MarketContext(code='YE',country_code='YE',name='Yemen',locale='ar-YE',timezone='Asia/Aden',default_currency='YER',status='active'); db.add(market); db.flush()
    db.add(MarketCurrency(market_id=market.id,currency='YER',is_default=True))
    db.add(MarketplaceFeeRule(market_id=market.id,name='Configured',scope='global',commission_bps=250,fixed_fee=Decimal('0'),currency='YER',active=True)); db.commit()
    with pytest.raises(MarketplaceError, match='client-supplied platform_fee_bps'):
        MarketplaceService(db).checkout(buyer.id,platform_fee_bps=500,market_id=market.id)
