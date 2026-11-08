from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.models.market import PaymentMethodCatalogEntry
from app.core.models.marketplace import MarketplaceCustomerOrder
from app.engines.marketplace import MarketplaceError
from app.api.routes.marketplace import CheckoutIn
from pydantic import ValidationError
from tests.test_marketplace_completion import setup


def _add_payment_methods(db, market_id):
    db.add_all([
        PaymentMethodCatalogEntry(
            market_id=market_id,
            code="cod",
            name="Cash on delivery",
            method_type="cod",
            requires_provider=False,
            active=True,
        ),
        PaymentMethodCatalogEntry(
            market_id=market_id,
            code="transfer",
            name="Manual transfer",
            method_type="transfer",
            requires_provider=True,
            active=True,
        ),
    ])
    db.commit()


def test_cod_selection_is_persisted_without_creating_provider_payment():
    db, seller, buyer, seller_user, listing, address, service = setup()
    _add_payment_methods(db, address.market_id)

    service.add_to_cart(buyer.id, listing.id, 1)
    order = service.checkout(buyer.id, address.id, Decimal("0"), None, None, None, payment_method_code="cod")[0]

    customer_order = db.get(MarketplaceCustomerOrder, order.customer_order_id)
    assert order.payment_method_code == "cod"
    assert customer_order.payment_method_code == "cod"
    assert order.payment_reference is None




def test_public_checkout_contract_requires_explicit_payment_method():
    with pytest.raises(ValidationError):
        CheckoutIn()

def test_cod_order_enters_processing_without_fabricating_payment():
    db, seller, buyer, seller_user, listing, address, service = setup()
    _add_payment_methods(db, address.market_id)
    service.add_to_cart(buyer.id, listing.id, 1)
    order = service.checkout(
        buyer.id, address.id, Decimal("0"), None, None, None,
        payment_method_code="cod",
    )[0]

    processing = service.mark_processing(seller.id, order.id)

    assert processing.status == "processing"
    assert processing.payment_reference is None
    assert processing.payment_method_code == "cod"


def test_unpaid_non_cod_order_cannot_enter_processing():
    db, seller, buyer, seller_user, listing, address, service = setup()
    service.add_to_cart(buyer.id, listing.id, 1)
    order = service.checkout(buyer.id, address.id)[0]

    with pytest.raises(MarketplaceError, match="captured-payment or COD"):
        service.mark_processing(seller.id, order.id)

def test_checkout_rejects_payment_method_not_active_in_market():
    db, seller, buyer, seller_user, listing, address, service = setup()
    _add_payment_methods(db, address.market_id)

    service.add_to_cart(buyer.id, listing.id, 1)
    with pytest.raises(MarketplaceError, match="payment method is not available"):
        service.checkout(buyer.id, address.id, Decimal("0"), None, None, None, payment_method_code="unknown")


def test_checkout_rejects_provider_backed_payment_without_certified_integration():
    db, seller, buyer, seller_user, listing, address, service = setup()
    _add_payment_methods(db, address.market_id)

    service.add_to_cart(buyer.id, listing.id, 1)
    with pytest.raises(MarketplaceError, match="requires a certified provider integration"):
        service.checkout(
            buyer.id,
            address.id,
            Decimal("0"),
            None,
            None,
            None,
            payment_method_code="transfer",
        )
