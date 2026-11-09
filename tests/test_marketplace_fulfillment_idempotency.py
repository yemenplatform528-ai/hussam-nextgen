from tests.market_test_support import ensure_market
from types import SimpleNamespace
from app.api.routes.marketplace import seller_orders
from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.contracts import StockMovement
from app.core.models.marketplace import MarketplaceSellerOrder, MarketplaceFulfillment, MarketplaceOrder, MarketplacePayout
from app.core.models.market import PaymentMethodCatalogEntry
from app.core.models.logistics import ShipmentCollection
from app.core.models.logistics import ShipmentEvent
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.marketplace import MarketplaceService, ListingInput
from app.engines.fulfillment import FulfillmentService


def setup():
    e = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(e)
    db = sessionmaker(e, expire_on_commit=False)(); market=ensure_market(db)
    ids = IdentityService(db)
    seller = ids.create_tenant('Seller'); buyer_t = ids.create_tenant('Buyer')
    admin = ids.create_user('seller', 'seller@example.com'); buyer = ids.create_user('buyer', 'buyer@example.com')
    ids.add_membership(admin.id, seller.id, 'owner'); ids.add_membership(buyer.id, buyer_t.id, 'owner')
    inv = InventoryProductionService(db)
    inv.create_item(seller.id, 'rice', 'Rice', 'unit'); inv.create_warehouse(seller.id, 'wh', 'Main')
    inv.record(seller.id, StockMovement('rice', 'wh', Decimal('10'), 'in', 'opening'))
    db.add(PaymentMethodCatalogEntry(market_id=market.id, code='cod', name='Cash on delivery', method_type='cod', requires_provider=False, active=True)); db.commit()
    m = MarketplaceService(db); m.register_seller(seller.id, 'seller', 'Seller'); m.review_seller_verification(seller.id, admin.id, 'approved')
    a = m.add_address(buyer.id, 'Home', 'Buyer', '700000000', 'Aden', 'Aden', 'Main')
    l = m.create_listing(seller.id, ListingInput('rice', 'Rice', '', 'product', 'YER', Decimal('1000'), 'rice', 'wh'))
    m.moderate_listing(l.id, admin.id, 'approved'); m.publish_listing(seller.id, l.id)
    m.add_to_cart(buyer.id, l.id, 1); order = m.checkout(buyer.id, a.id, payment_method_code='cod')[0]
    so = db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id == order.id))
    order = m.mark_processing(seller.id, order.id)
    db.refresh(so)
    assert order.status == 'processing' and so.status == 'processing'
    assert order.payment_reference is None
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

def test_cod_selection_becomes_shipment_collection_amount():
    db, fs, seller, f, shipment = setup()
    assert shipment.cod_amount == Decimal('1000.0000')
    fs.transition(seller.id, f.id, 'picked_up', event_id='cod-pick')
    fs.transition(seller.id, f.id, 'in_transit', event_id='cod-transit')
    fs.transition(seller.id, f.id, 'out_for_delivery', event_id='cod-out')
    fs.transition(seller.id, f.id, 'delivered', event_id='cod-delivered')
    seller_order = db.get(MarketplaceSellerOrder, f.seller_order_id)
    order = db.get(MarketplaceOrder, seller_order.marketplace_order_id)
    marketplace = MarketplaceService(db)
    marketplace.mark_shipped(seller.id, order.id, shipment.id)
    marketplace.mark_delivered(seller.id, order.id, shipment.id)
    from app.engines.logistics import LogisticsProductionService
    collected = LogisticsProductionService(db).create_cod_collection(
        seller.id, shipment.id, reference='COD-COL-1', amount=Decimal('1000'), currency='YER'
    )
    assert collected.status == 'collected'
    assert collected.amount == Decimal('1000.0000')
    assert collected.evidence_source == 'seller_attestation'
    assert collected.independently_verified is False
    replay = LogisticsProductionService(db).create_cod_collection(
        seller.id, shipment.id, reference='COD-COL-1', amount=Decimal('1000'), currency='YER'
    )
    assert replay.id == collected.id
    payout = db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == order.id))
    assert order.status == 'completed'
    assert payout.status == 'held'
    seller_view = seller_orders(ctx=SimpleNamespace(role='owner', tenant_id=seller.id), db=db)
    seller_order_view = next(item for item in seller_view['items'] if item['id'] == order.id)
    assert seller_order_view['fulfillment_id'] == f.id
    assert seller_order_view['shipment_id'] == shipment.id
    assert seller_order_view['cod_collection_evidence_source'] == 'seller_attestation'
    assert seller_order_view['cod_collection_independently_verified'] is False
    assert seller_order_view['cod_collection_status'] == 'collected'
