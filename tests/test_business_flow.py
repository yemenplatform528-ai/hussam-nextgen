from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership, Journal
from app.core.models.finance import FiscalPeriod
from app.core.models.inventory import InventoryMovementRecord, InventoryReservation
from app.core.models.payments import PaymentIntent
from app.core.models.logistics import Shipment
from app.engines.procurement.production import ProcurementProductionService, PurchaseLineInput, ReceiptLineInput
from app.engines.commerce import CommerceProductionService, OrderLineInput
from app.engines.payments import PaymentProductionService
from app.engines.logistics import LogisticsProductionService


def test_complete_business_flow_from_purchase_to_settlement():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True,
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    with Factory() as db:
        tenant = Tenant(id=1, name="Demo Business", status="active")
        user = User(id="u1", email="owner@example.com", active=True)
        membership = TenantMembership(user_id="u1", tenant_id=1, role="owner", active=True)
        period = FiscalPeriod(tenant_id=1, name="2026", starts_on=date(2026, 1, 1),
                              ends_on=date(2026, 12, 31), closed=False)
        db.add_all([tenant, user, membership, period])
        db.commit()

        procurement = ProcurementProductionService(db)
        inventory = __import__("app.engines.inventory.production", fromlist=["InventoryProductionService"]).InventoryProductionService(db)
        commerce = CommerceProductionService(db)
        payments = PaymentProductionService(db)
        logistics = LogisticsProductionService(db)

        inventory.create_item(1, "item-1", "Product A", "unit")
        inventory.create_warehouse(1, "wh-1", "Main Warehouse", False)
        procurement.create_supplier(1, "sup-1", "Supplier A")

        # 1) Purchase -> receive -> inventory IN + accounting.
        po = procurement.create_draft(
            1, "PO-001", "sup-1", "wh-1", "YER",
            [PurchaseLineInput("item-1", Decimal("10"), Decimal("100"))],
        )
        procurement.confirm(1, po.id)
        line_id = db.scalar(select(__import__("app.core.models.procurement", fromlist=["PurchaseOrderLine"]).PurchaseOrderLine.id)
                             .where(__import__("app.core.models.procurement", fromlist=["PurchaseOrderLine"]).PurchaseOrderLine.order_id == po.id))
        receipt = procurement.receive(
            1, po.id, "GRN-001", [ReceiptLineInput(line_id, Decimal("10"))],
            posting_date=date(2026, 9, 10), post_accounting=True, actor_id="u1",
        )
        assert receipt.reference == "GRN-001"

        stock = inventory.snapshot(1, "item-1", "wh-1")
        assert stock.on_hand == Decimal("10.0000")
        assert stock.available == Decimal("10.0000")
        assert db.scalar(select(Journal).where(Journal.tenant_id == 1, Journal.reference == "GRN:GRN-001")) is not None

        # 2) Sale -> reserve -> fulfill -> inventory OUT.
        order = commerce.create_draft(
            1, "SO-001", "wh-1", "YER",
            [OrderLineInput("item-1", Decimal("2"), Decimal("150"))],
        )
        commerce.confirm(1, order.id)
        stock = inventory.snapshot(1, "item-1", "wh-1")
        assert stock.on_hand == Decimal("10.0000")
        assert stock.reserved == Decimal("2.0000")
        assert stock.available == Decimal("8.0000")
        commerce.fulfill(1, order.id)
        stock = inventory.snapshot(1, "item-1", "wh-1")
        assert stock.on_hand == Decimal("8.0000")
        assert stock.reserved == Decimal("0.0000")

        # 3) Payment -> provider verification -> capture -> settlement.
        payment = payments.create_intent(1, "PAY-001", "test-provider", Decimal("300"), "YER")
        payments.mark_processing(1, payment.reference)
        payments.process_webhook(
            1, provider="test-provider", event_id="evt-001", event_type="payment.authorized",
            payment_reference=payment.reference, provider_payment_id="prov-001", status="authorized",
            payload={"verified": True},
        )
        captured = payments.capture(1, payment.reference, posting_date=date(2026, 9, 10), actor_id="u1")
        assert captured.status == "captured"
        settlement = payments.settle(
            1, payment.reference, settlement_reference="SET-001", actual_amount=Decimal("300"),
            currency="YER", posting_date=date(2026, 9, 10), actor_id="u1",
        )
        assert settlement.status == "settled"

        # 4) Shipment -> tracking -> delivery.
        shipment = logistics.create_shipment(
            1, order_id=order.id, reference="SHP-001", origin_warehouse_id="wh-1",
            destination="Aden", carrier="Hussam Logistics", currency="YER",
            tracking_number="TRK-001", cod_amount=Decimal("0"),
        )
        logistics.transition(1, shipment.id, "picked_up", event_id="ship-evt-1")
        logistics.transition(1, shipment.id, "in_transit", event_id="ship-evt-2")
        logistics.transition(1, shipment.id, "out_for_delivery", event_id="ship-evt-3")
        delivered = logistics.transition(1, shipment.id, "delivered", event_id="ship-evt-4")
        assert delivered.status == "delivered"

        # 5) Cross-engine final assertions.
        assert db.scalar(select(PaymentIntent).where(PaymentIntent.reference == "PAY-001")).status == "captured"
        assert db.scalar(select(Shipment).where(Shipment.reference == "SHP-001")).status == "delivered"
        assert db.scalar(select(InventoryReservation).where(InventoryReservation.reference.like("order:%"))) .status == "fulfilled"
        assert db.scalar(select(InventoryMovementRecord).where(InventoryMovementRecord.reference == "order:1:line:1:fulfill")) is not None
        assert db.scalar(select(Journal).where(Journal.reference == "PAY:PAY-001:capture")) is not None
        assert db.scalar(select(Journal).where(Journal.reference == "SET:SET-001")) is not None
