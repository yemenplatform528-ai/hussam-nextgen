from pydantic import ValidationError
import pytest
from decimal import Decimal
from app.engines.marketplace import MarketplaceService, ListingInput
from app.api.routes.marketplace import SellerIn, VerificationSubmissionIn
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


def test_seller_onboarding_contract_validates_slug_type_and_review_notes():
    with pytest.raises(ValidationError):
        SellerIn(slug='Taiz Market', display_name='متجر تعز')
    with pytest.raises(ValidationError):
        SellerIn(slug='taiz-market', display_name='متجر تعز', seller_type='unknown')
    with pytest.raises(ValidationError):
        VerificationSubmissionIn(notes='x' * 4001)
    valid = SellerIn(slug='taiz-market-1', display_name='متجر تعز', seller_type='business')
    assert valid.slug == 'taiz-market-1'


def test_seller_registration_and_verification_remain_pending_until_platform_review():
    db, seller, buyer_t, buyer, su = setup()
    service = MarketplaceService(db)
    assert service.seller_center(seller.id)['registered'] is False
    registered = service.register_seller(seller.id, 'taiz-market-1', 'متجر تعز', seller_type='business')
    verification = service.submit_seller_verification(seller.id, 'نشاط بيع مواد غذائية داخل تعز')
    view = service.seller_center(seller.id)
    assert registered.status == 'pending'
    assert verification.status == 'pending'
    assert view['registered'] is True
    assert view['seller']['verification'] == 'pending'
