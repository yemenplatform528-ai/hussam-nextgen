from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.models import (
    Base,
    MarketContext,
    MarketCurrency,
    MarketGeography,
    MarketCoverage,
    MarketMoneyUnit,
    PaymentMethodCatalogEntry,
    MarketplaceAddress,
    MarketplaceSellerProfile,
    MarketplaceShippingRate,
    Tenant,
)
from app.core.services.yemen_checkout_context import YemenCheckoutContextService
from app.engines.marketplace import MarketplaceService, MarketplaceError
from app.api.routes.platform import client_market_geography


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)()


def seed():
    db = make_db()
    market = MarketContext(
        id=1, code="YEM", country_code="YE", name="Yemen",
        locale="ar-YE", timezone="Asia/Aden", default_currency="YER",
        status="active",
    )
    db.add(market)
    db.flush()
    root = MarketGeography(id=10, market_id=1, code="YE", level="country", name="Yemen")
    gov = MarketGeography(
        id=11, market_id=1, parent_id=10, code="YE-ADN",
        level="governorate", name="Aden", name_ar="عدن",
    )
    district = MarketGeography(
        id=12, market_id=1, parent_id=11, code="YE-ADN-KHM",
        level="district", name="Khor Maksar", name_ar="خور مكسر",
    )
    db.add_all([root, gov, district])
    db.flush()
    db.add(MarketCoverage(market_id=1, geography_id=11, status="available"))
    db.add(MarketCurrency(market_id=1, currency="YER", is_default=True))
    db.add(MarketMoneyUnit(
        market_id=1, code="YER-CURRENT", currency="YER",
        variant="current", name="Yemeni rial", name_ar="ريال يمني",
    ))
    db.add(PaymentMethodCatalogEntry(
        market_id=1, code="cod", name="Cash on delivery",
        method_type="cod", requires_provider=False, active=True,
    ))
    db.add(PaymentMethodCatalogEntry(
        market_id=1, code="transfer", name="Manual transfer",
        method_type="transfer", requires_provider=True, active=True,
    ))
    address = MarketplaceAddress(
        id=20, user_id="buyer", label="Home", recipient_name="Buyer",
        phone="700000000", governorate="Aden", city="Khor Maksar",
        address_line="Main road", country_code="YE", market_id=1,
        governorate_id=11, district_id=12, address_confidence="high",
    )
    db.add(Tenant(id=77, name="Seller 77", status="active"))
    db.add(MarketplaceSellerProfile(
        tenant_id=77, slug="seller-77", display_name="Seller 77", status="active",
    ))
    db.add(address)
    db.add(MarketplaceShippingRate(
        seller_tenant_id=77, market_id=1, governorate="Aden",
        city="Khor Maksar", governorate_id=11, district_id=12,
        currency="YER", fee=Decimal("250"), active=True,
    ))
    db.commit()
    return db



def test_address_geography_resolves_and_validates_full_parent_chain():
    db = seed()
    db.add(MarketGeography(id=13, market_id=1, parent_id=12, code='YE-ADN-KHM-LOC', level='locality', name='Locality', name_ar='محلة'))
    db.add(MarketGeography(id=14, market_id=1, parent_id=10, code='YE-TAZ', level='governorate', name='Taiz', name_ar='تعز'))
    db.add(MarketGeography(id=15, market_id=1, parent_id=14, code='YE-TAZ-CAI', level='district', name='Al Qahirah', name_ar='القاهرة'))
    db.add(MarketGeography(id=16, market_id=1, parent_id=10, code='YE-BAD-DISTRICT', level='district', name='Invalid parent', name_ar='أب'))
    db.commit()
    service = MarketplaceService(db)

    governorate_id, district_id, locality_id, nodes = service._resolve_geography(1, locality_id=13)
    assert (governorate_id, district_id, locality_id) == (11, 12, 13)
    assert nodes['governorate_id'].name == 'Aden'

    with pytest.raises(MarketplaceError, match='district does not belong to governorate'):
        service._resolve_geography(1, governorate_id=11, district_id=15)
    with pytest.raises(MarketplaceError, match='district parent governorate is invalid'):
        service._resolve_geography(1, district_id=16)


def test_market_geography_endpoint_is_market_scoped_and_hierarchical():
    db = seed()
    govs = client_market_geography('YEM', level='governorate', db=db)
    assert govs['items'][0]['id'] == 11
    districts = client_market_geography('YEM', level='district', parent_id=11, db=db)
    assert districts['items'][0]['id'] == 12
    with pytest.raises(Exception, match='parent geography not found'):
        client_market_geography('YEM', level='district', parent_id=999, db=db)

def test_checkout_context_is_explicit_and_cod_first_class():
    db = seed()
    result = YemenCheckoutContextService(db).build(
        "YEM", user_id="buyer", address_id=20, seller_tenant_ids=[77],
    )
    assert result["schema_version"] == "1.0"
    assert result["market"]["code"] == "YEM"
    assert result["money"] == {
        "currency": "YER",
        "label": "ريال يمني",
        "conversion": {"required_source_context": True, "automatic_conversion": False},
    }
    assert result["payments"]["cod"]["available"] is True
    assert {x["code"] for x in result["payments"]["methods"]} == {"cod", "transfer"}
    methods = {x["code"]: x for x in result["payments"]["methods"]}
    assert methods["cod"]["available"] is True
    assert methods["transfer"]["available"] is False
    assert result["delivery"]["destination"]["coverage"] == "available"
    assert result["sellers"][0]["delivery"]["available"] is True


def test_checkout_context_never_accepts_another_users_address():
    db = seed()
    with pytest.raises(ValueError, match="delivery address"):
        YemenCheckoutContextService(db).build("YEM", user_id="other-user", address_id=20)


def test_checkout_context_rejects_inactive_market():
    db = seed()
    db.query(MarketContext).filter(MarketContext.id == 1).update({"status": "suspended"})
    db.commit()
    with pytest.raises(ValueError, match="market is not active"):
        YemenCheckoutContextService(db).build("YEM")



def test_checkout_context_rejects_inactive_seller():
    db = seed()
    db.query(MarketplaceSellerProfile).filter(
        MarketplaceSellerProfile.tenant_id == 77
    ).update({"status": "suspended"})
    db.commit()
    with pytest.raises(ValueError, match="seller is not active"):
        YemenCheckoutContextService(db).build("YEM", seller_tenant_ids=[77])


def test_checkout_context_rejects_unknown_seller():
    db = seed()
    with pytest.raises(ValueError, match="seller is not active"):
        YemenCheckoutContextService(db).build("YEM", seller_tenant_ids=[999])
