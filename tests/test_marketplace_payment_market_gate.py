from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.market import MarketContext, MarketCurrency, ProviderRegistryEntry, ProviderMarketCapability
from app.core.models.marketplace import MarketplaceCustomerOrder
from app.engines.payments import PaymentProductionService, PaymentError
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from tests.market_test_support import ensure_market
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement


def test_internal_marketplace_payment_intent_requires_market_provider_gate():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    market=ensure_market(db)
    db.query(ProviderRegistryEntry).filter_by(code='test-provider').delete(); db.commit()
    svc=PaymentProductionService(db)
    with pytest.raises(PaymentError, match='provider production gate blocked'):
        svc.create_intent(1,'PAY-GATE','test-provider',Decimal('100'),'YER',market_id=market.id)


def test_marketplace_attach_payment_intent_passes_order_market_to_provider_gate():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)(); ensure_market(db)
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer'); buyer=ids.create_user('buyer','buyer-gate@example.com'); admin=ids.create_user('seller','seller-gate@example.com')
    ids.add_membership(buyer.id,buyer_t.id,'owner'); ids.add_membership(admin.id,seller.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice-gate','Rice','bag'); inv.create_warehouse(seller.id,'wh-gate','Main'); inv.record(seller.id,StockMovement('rice-gate','wh-gate',Decimal('10'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller-gate','Seller'); m.review_seller_verification(seller.id,admin.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice-gate','Rice','','product','YER',Decimal('1000'),'rice-gate','wh-gate')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,1); order=m.checkout(buyer.id)[0]
    db.query(ProviderRegistryEntry).filter_by(code='test-provider').delete(); db.commit()
    with pytest.raises(PaymentError, match='provider production gate blocked'):
        m.attach_payment_intent(buyer.id,order.id,'test-provider')
