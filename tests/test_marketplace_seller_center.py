from decimal import Decimal
from app.engines.marketplace import MarketplaceService, ListingInput
from tests.test_marketplace import setup


def test_seller_center_returns_operational_metrics_and_actions():
    db, seller, buyer_t, buyer, su = setup()
    m = MarketplaceService(db)
    m.register_seller(seller.id, 'center-seller', 'Center Seller')
    m.review_seller_verification(seller.id, su.id, 'approved')
    listing = m.create_listing(seller.id, ListingInput('rice', 'Rice', '', 'product', 'YER', Decimal('1000'), 'rice', 'wh'))
    view = m.seller_center(seller.id)
    assert view['registered'] is True
    assert view['seller']['status'] == 'active'
    assert view['seller']['verification'] == 'approved'
    assert view['metrics']['listings_total'] == 1
    assert view['metrics']['listings_published'] == 0
    assert any(a['key'] == 'moderation' for a in view['actions'])


def test_seller_center_is_tenant_scoped():
    db, seller, buyer_t, buyer, su = setup()
    m = MarketplaceService(db)
    other = buyer_t
    m.register_seller(seller.id, 'center-seller', 'Center Seller')
    m.review_seller_verification(seller.id, su.id, 'approved')
    m.create_listing(seller.id, ListingInput('rice', 'Rice', '', 'product', 'YER', Decimal('1000'), 'rice', 'wh'))
    own = m.seller_center(seller.id)
    other_view = m.seller_center(other.id)
    assert own['metrics']['listings_total'] == 1
    assert other_view['registered'] is False
