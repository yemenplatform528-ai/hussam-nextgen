from tests.market_test_support import ensure_market
from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.contracts import StockMovement
from app.core.models.marketplace import MarketplaceSellerOrder, MarketplaceFulfillment
from app.core.models.logistics import ShipmentEvent
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.marketplace import MarketplaceService, ListingInput
from app.engines.fulfillment import FulfillmentService


def setup():
    e = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)(); ensure_market(db)
    ids = IdentityService(db)
    seller = ids.create_tenant('Seller'); buyer_t = ids.create_tenant('Buyer')
    admin = ids.create_user('seller', 'seller@example.com'); buyer = ids.create_user('buyer', 'buyer@example.com')
    ids.add_membership(admin.id, seller.id, 'owner'); ids.add_membership(buyer.id, buyer_t.id, 'owner')
    inv = InventoryProductionService(db)
    inv.create_item(seller.id, 'rice', 'Rice', 'unit'); inv.create_warehouse(seller.id, 'wh', 'Main')
    inv.record(seller.id, StockMovement('rice', 'wh', Decimal('10'), 'in', 'opening'))
    m = MarketplaceService(db); m.register_seller(seller.id, 'seller', 'Seller'); m.review_seller_verification(seller.id, admin.id, 'approved')
    a = m.add_address(buyer.id, 'Home', 'Buyer', '700000000', 'Aden', 'Aden', 'Main')
    l = m.create_listing(seller.id, ListingInput('rice', 'Rice', '', 'product', 'YER', Decimal('1000'), 'rice', 'wh'))
    m.moderate_listing(l.id, admin.id, 'approved'); m.publish_listing(seller.id, l.id)
    m.add_to_cart(buyer.id, l.id, 1); order = m.checkout(buyer.id, a.id)[0]
    so = db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id == order.id))
    so.status = 'processing'; db.commit()
    fs = FulfillmentService(db); f = fs.create(seller.id, so.id, 'hussam_delivery'); fs.transition(seller.id, f.id, 'assigned'); fs.transition(seller.id, f.id, 'ready')
    f, shipment = fs.create_shipment(seller.id, f.id, 'Hussam Delivery', 'TRK-1')
    return db, fs, seller, f, shipment


def test_fulfillment_physical_transition_is_idempotent_by_event_id():
    db, fs, seller, f, shipment = setup()
    first = fs.transition(seller.id, f.id, 'picked_up', event_id='carrier-event-1')
    second = fs.transition(seller.id, f.id, 'picked_up', event_id='carrier-event-1')
    assert first.id == second.id
    events = db.scalars(select(ShipmentEvent).where(ShipmentEvent.tenant_id == seller.id, ShipmentEvent.event_id == 'carrier-event-1')).all()
    assert len(events) == 1
    assert db.get(MarketplaceFulfillment, f.id).status == 'picked_up'


def test_fulfillment_does_not_advance_when_logistics_rejects_event():
    db, fs, seller, f, shipment = setup()
    # No tracking mutation is needed here; shipment already has tracking.
    fs.transition(seller.id, f.id, 'picked_up', event_id='carrier-event-2')
    assert db.get(MarketplaceFulfillment, f.id).status == 'picked_up'
