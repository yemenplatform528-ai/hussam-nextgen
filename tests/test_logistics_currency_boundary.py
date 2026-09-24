from decimal import Decimal
import pytest

from app.engines.logistics import LogisticsError
from tests.test_logistics_production import setup


def test_create_shipment_rejects_currency_mismatch_with_order():
    s, tenant, order, logistics = setup()
    with pytest.raises(LogisticsError, match="currency must match order currency"):
        logistics.create_shipment(
            tenant.id,
            order_id=order.id,
            reference="SHP-CURRENCY",
            origin_warehouse_id="wh-a",
            destination="Aden",
            carrier="local",
            currency="SAR",
            cod_amount=Decimal("0"),
        )
