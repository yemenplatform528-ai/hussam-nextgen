from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant
from app.core.models.marketplace import MarketplacePayout
from app.engines.identity import IdentityService
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from tests.market_test_support import ensure_market

def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ensure_market(db)
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer'); admin=ids.create_user('admin','admin@example.com'); buyer=ids.create_user('buyer','buyer@example.com')
    ids.add_membership(admin.id,seller.id,'owner'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main'); inv.record(seller.id,StockMovement('rice','wh',Decimal('20'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller-snapshot','Seller Snapshot'); m.review_seller_verification(seller.id,admin.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.ensure_buyer(buyer.id); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id)[0]; o.status='completed'; db.commit()
    p=db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id)); p.status='eligible'; p.eligible_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); m._balance_entry(p,'credit',p.net_amount,'settlement:SET-DEST'); p.payment_reference='PAY-DEST'; p.settlement_reference='SET-DEST'; db.commit()
    return db,seller,buyer,admin,m,o

def test_payout_binds_destination_at_request_and_rejects_change():
    db,seller,buyer,admin,m,o=setup()
    m.set_payout_destination(seller.id,'test-provider','DEST-A'); m.verify_payout_destination(seller.id,admin.id)
    p=m.request_payout(seller.id,o.id)
    assert p.payout_provider=='test-provider'; assert p.payout_destination_reference=='DEST-A'
    m.set_payout_destination(seller.id,'test-provider','DEST-B')
    destination = db.query(__import__('app.core.models.marketplace', fromlist=['MarketplacePayoutDestination']).MarketplacePayoutDestination).filter_by(seller_tenant_id=seller.id).one()
    destination.status='verified'
    db.commit()
    with pytest.raises(MarketplaceError, match='destination changed'):
        m.mark_payout_paid(seller.id,o.id,'EXT-DEST')
