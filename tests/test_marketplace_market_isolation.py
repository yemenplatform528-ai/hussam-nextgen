from decimal import Decimal
import pytest
from sqlalchemy import select

from app.core.models.market import MarketContext, MarketCurrency, MarketGeography
from app.core.models.marketplace import MarketplaceAddress, MarketplaceFeeRule, MarketplaceListing, MarketplaceCart, MarketplaceCartItem
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from tests.test_marketplace import setup


def markets(db):
    a = MarketContext(code='YE-A', country_code='YE', name='Yemen A', locale='ar-YE', timezone='Asia/Aden', default_currency='YER', status='active')
    b = MarketContext(code='YE-B', country_code='YE', name='Yemen B', locale='ar-YE', timezone='Asia/Aden', default_currency='USD', status='active')
    db.add_all([a, b]); db.flush()
    db.add_all([
        MarketCurrency(market_id=a.id, currency='YER', is_default=True),
        MarketCurrency(market_id=b.id, currency='USD', is_default=True),
    ])
    db.commit()
    return a, b


def test_multiple_markets_require_explicit_context_and_isolate_listing_visibility():
    db, seller, buyer_t, buyer, seller_user = setup()
    a, b = markets(db)
    m = MarketplaceService(db)
    m.register_seller(seller.id, 'seller', 'Seller')
    m.review_seller_verification(seller.id, seller_user.id, 'approved')
    a_listing = m.create_listing(seller.id, ListingInput('a', 'Market A', '', 'service', 'YER', Decimal('100'), market_id=a.id))
    m.moderate_listing(a_listing.id, seller_user.id, 'approved'); m.publish_listing(seller.id, a_listing.id)
    assert len(m.public_listings(market_id=a.id)) == 1
    assert m.public_listings(market_id=b.id) == []
    with pytest.raises(MarketplaceError, match='market context is required'):
        m.public_listings()


def test_market_currency_is_enforced_at_listing_creation():
    db, seller, buyer_t, buyer, seller_user = setup()
    a, b = markets(db)
    m = MarketplaceService(db); m.register_seller(seller.id, 'seller2', 'Seller 2'); m.review_seller_verification(seller.id, seller_user.id, 'approved')
    with pytest.raises(MarketplaceError, match='currency is not enabled'):
        m.create_listing(seller.id, ListingInput('bad', 'Bad', '', 'service', 'USD', Decimal('100'), market_id=a.id))


def test_shipping_rate_is_market_scoped_and_address_market_is_checked_at_checkout():
    db, seller, buyer_t, buyer, seller_user = setup()
    a, b = markets(db)
    m = MarketplaceService(db); m.register_seller(seller.id, 'seller3', 'Seller 3'); m.review_seller_verification(seller.id, seller_user.id, 'approved')
    listing = m.create_listing(seller.id, ListingInput('service-a', 'Service A', '', 'service', 'YER', Decimal('100'), market_id=a.id))
    m.moderate_listing(listing.id, seller_user.id, 'approved'); m.publish_listing(seller.id, listing.id)
    address = MarketplaceAddress(user_id=buyer.id, label='A', recipient_name='Buyer', phone='700000000', governorate='A', city='A', address_line='A', market_id=b.id, address_confidence='high')
    db.add(address); db.commit()
    m.add_to_cart(buyer.id, listing.id, 1)
    with pytest.raises(MarketplaceError, match='shipping address does not belong'):
        m.checkout(buyer.id, shipping_address_id=address.id)


def test_structured_shipping_geography_and_per_market_carts_are_isolated():
    db, seller, buyer_t, buyer, seller_user = setup()
    a, b = markets(db)
    country = MarketGeography(market_id=a.id, code='YE', level='country', name='Yemen', status='active')
    db.add(country); db.flush()
    gov = MarketGeography(market_id=a.id, parent_id=country.id, code='AD', level='governorate', name='Aden', status='active')
    db.add(gov); db.flush()
    district = MarketGeography(market_id=a.id, parent_id=gov.id, code='KOR', level='district', name='Khor Maksar', status='active')
    db.add(district); db.commit()

    m = MarketplaceService(db)
    m.register_seller(seller.id, 'seller-geo', 'Seller Geo')
    m.review_seller_verification(seller.id, seller_user.id, 'approved')
    la = m.create_listing(seller.id, ListingInput('geo-a', 'Geo A', '', 'service', 'YER', Decimal('100'), market_id=a.id))
    lb = m.create_listing(seller.id, ListingInput('geo-b', 'Geo B', '', 'service', 'USD', Decimal('10'), market_id=b.id))
    for listing in (la, lb):
        m.moderate_listing(listing.id, seller_user.id, 'approved'); m.publish_listing(seller.id, listing.id)

    address = m.add_address(buyer.id, 'Home', 'Buyer', '700000000', 'Aden', 'Khor Maksar', 'Street 1', market_id=a.id, governorate_id=gov.id, district_id=district.id, address_confidence='high')
    rate = m.add_shipping_rate(seller.id, 'Aden', 'Khor Maksar', 'YER', Decimal('250'), market_id=a.id, governorate_id=gov.id, district_id=district.id)
    quote = m.quote_shipping(buyer.id, address.id, seller.id, 'YER')
    assert quote.fee == Decimal('250.0000') and quote.market_id == a.id and rate.governorate_id == gov.id

    m.add_to_cart(buyer.id, la.id, 1)
    m.add_to_cart(buyer.id, lb.id, 1)
    carts = db.scalars(select(MarketplaceCart).where(MarketplaceCart.buyer_user_id == buyer.id, MarketplaceCart.status == 'active')).all()
    assert {x.market_id for x in carts} == {a.id, b.id}


def test_checkout_requires_market_when_buyer_has_multiple_active_carts():
    db, seller, buyer_t, buyer, seller_user = setup()
    a, b = markets(db)
    m = MarketplaceService(db)
    m.register_seller(seller.id, 'seller-checkout-market', 'Seller Checkout Market')
    m.review_seller_verification(seller.id, seller_user.id, 'approved')
    la = m.create_listing(seller.id, ListingInput('checkout-a', 'Checkout A', '', 'service', 'YER', Decimal('100'), market_id=a.id))
    lb = m.create_listing(seller.id, ListingInput('checkout-b', 'Checkout B', '', 'service', 'USD', Decimal('10'), market_id=b.id))
    for listing in (la, lb):
        m.moderate_listing(listing.id, seller_user.id, 'approved'); m.publish_listing(seller.id, listing.id)
    m.add_to_cart(buyer.id, la.id, 1)
    m.add_to_cart(buyer.id, lb.id, 1)
    with pytest.raises(MarketplaceError, match='market context is required'):
        m.checkout(buyer.id)
    orders = m.checkout(buyer.id, market_id=a.id)
    assert len(orders) == 1 and orders[0].market_id == a.id
    carts = db.scalars(select(MarketplaceCart).where(MarketplaceCart.buyer_user_id == buyer.id, MarketplaceCart.status == 'active')).all()
    assert {x.market_id for x in carts} == {a.id, b.id}
    b_cart = next(x for x in carts if x.market_id == b.id)
    assert db.scalar(select(MarketplaceCartItem).where(MarketplaceCartItem.cart_id == b_cart.id)) is not None
