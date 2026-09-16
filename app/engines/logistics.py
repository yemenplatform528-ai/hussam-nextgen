from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.commerce import SalesOrder
from app.core.models.logistics import Shipment, ShipmentEvent, ShipmentCollection
from app.core.models.governance import OutboxEvent

class LogisticsError(ValueError):
    pass

@dataclass(frozen=True)
class ShipmentStatus:
    value: str

_ALLOWED = {
    'ready': {'picked_up', 'cancelled'},
    'picked_up': {'in_transit', 'failed'},
    'in_transit': {'out_for_delivery', 'failed', 'returned'},
    'out_for_delivery': {'delivered', 'failed', 'returned'},
    'delivered': set(),
    'failed': {'picked_up', 'cancelled', 'returned'},
    'cancelled': set(),
    'returned': set(),
}

class LogisticsProductionService:
    """Shipment lifecycle and tracking. It emits facts; Payments/Finance remain authoritative for money."""
    def __init__(self, db: Session):
        self.db = db

    def _event(self, tenant_id, event_type, aggregate_id, payload):
        from uuid import uuid4
        self.db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type,
            aggregate_type='shipment', aggregate_id=str(aggregate_id), payload=payload, published=False))

    def _shipment(self, tenant_id, shipment_id, lock=False):
        q = select(Shipment).where(Shipment.id == shipment_id, Shipment.tenant_id == tenant_id)
        if lock: q = q.with_for_update()
        s = self.db.scalar(q)
        if s is None: raise LogisticsError('shipment not found in tenant')
        return s

    def create_shipment(self, tenant_id: int, *, order_id: int, reference: str,
                        origin_warehouse_id: str, destination: str, carrier: str,
                        currency: str, cod_amount: Decimal = Decimal('0'), tracking_number: str | None = None) -> Shipment:
        amount = Decimal(str(cod_amount))
        if tenant_id <= 0 or order_id <= 0 or not reference or not origin_warehouse_id or not destination or not carrier or not currency:
            raise LogisticsError('shipment identity and routing fields are required')
        if amount < 0: raise LogisticsError('COD amount cannot be negative')
        order = self.db.scalar(select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id))
        if order is None: raise LogisticsError('order not found in tenant')
        if order.status != 'fulfilled': raise LogisticsError('only fulfilled orders can be shipped')
        if order.warehouse_id != origin_warehouse_id: raise LogisticsError('shipment origin must match order warehouse')
        if Decimal(str(order.total)) < amount: raise LogisticsError('COD amount cannot exceed order total')
        if self.db.scalar(select(Shipment).where(Shipment.tenant_id == tenant_id, Shipment.reference == reference)):
            raise LogisticsError('duplicate shipment reference')
        if tracking_number and self.db.scalar(select(Shipment).where(Shipment.tenant_id == tenant_id, Shipment.tracking_number == tracking_number)):
            raise LogisticsError('duplicate tracking number')
        s = Shipment(tenant_id=tenant_id, order_id=order_id, reference=reference,
                     origin_warehouse_id=origin_warehouse_id, destination=destination, carrier=carrier,
                     tracking_number=tracking_number, status='ready', cod_amount=amount, currency=currency)
        self.db.add(s); self.db.flush()
        self._event(tenant_id, 'logistics.shipment.created', s.id,
                    {'reference': reference, 'order_id': order_id, 'carrier': carrier, 'tracking_number': tracking_number})
        try:
            self.db.commit(); self.db.refresh(s); return s
        except IntegrityError:
            self.db.rollback(); raise LogisticsError('duplicate shipment reference or tracking number')

    def assign_tracking(self, tenant_id: int, shipment_id: int, tracking_number: str) -> Shipment:
        if not tracking_number: raise LogisticsError('tracking number is required')
        s = self._shipment(tenant_id, shipment_id, lock=True)
        if s.status in {'delivered','cancelled','returned'}: raise LogisticsError('terminal shipment cannot be changed')
        if s.tracking_number and s.tracking_number != tracking_number: raise LogisticsError('tracking number cannot be changed')
        conflict = self.db.scalar(select(Shipment).where(Shipment.tenant_id == tenant_id, Shipment.tracking_number == tracking_number, Shipment.id != shipment_id))
        if conflict: raise LogisticsError('tracking number already belongs to another shipment')
        s.tracking_number = tracking_number; s.updated_at = datetime.now(timezone.utc)
        self._event(tenant_id, 'logistics.shipment.tracking_assigned', s.id, {'tracking_number': tracking_number})
        try: self.db.commit(); return s
        except IntegrityError:
            self.db.rollback(); raise LogisticsError('tracking number conflict')

    def transition(self, tenant_id: int, shipment_id: int, new_status: str, *, event_id: str,
                   location: str | None = None, note: str | None = None, occurred_at: datetime | None = None) -> Shipment:
        if new_status not in _ALLOWED: raise LogisticsError('unsupported shipment status')
        if not event_id: raise LogisticsError('event id is required')
        existing = self.db.scalar(select(ShipmentEvent).where(ShipmentEvent.tenant_id == tenant_id, ShipmentEvent.event_id == event_id))
        if existing: return self._shipment(tenant_id, shipment_id)
        s = self._shipment(tenant_id, shipment_id, lock=True)
        if new_status not in _ALLOWED[s.status]: raise LogisticsError(f'invalid shipment transition: {s.status} -> {new_status}')
        if new_status in {'picked_up','in_transit','out_for_delivery'} and not s.tracking_number:
            raise LogisticsError('tracking number required before transit')
        when = occurred_at or datetime.now(timezone.utc)
        self.db.add(ShipmentEvent(tenant_id=tenant_id, shipment_id=s.id, event_id=event_id,
                                  event_type=new_status, location=location, note=note, occurred_at=when))
        s.status = new_status; s.updated_at = datetime.now(timezone.utc)
        self._event(tenant_id, f'logistics.shipment.{new_status}', s.id,
                    {'reference': s.reference, 'event_id': event_id, 'location': location})
        try:
            self.db.commit(); return s
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(select(ShipmentEvent).where(ShipmentEvent.tenant_id == tenant_id, ShipmentEvent.event_id == event_id))
            if existing: return self._shipment(tenant_id, shipment_id)
            raise LogisticsError('tracking event conflict')

    def create_cod_collection(self, tenant_id: int, shipment_id: int, *, reference: str,
                              amount: Decimal, currency: str) -> ShipmentCollection:
        amount = Decimal(str(amount))
        s = self._shipment(tenant_id, shipment_id, lock=True)
        if s.cod_amount <= 0: raise LogisticsError('shipment has no COD amount')
        if s.status != 'delivered': raise LogisticsError('COD can only be collected after delivery')
        if amount != Decimal(str(s.cod_amount)) or currency != s.currency:
            raise LogisticsError('collection amount/currency must match COD')
        if self.db.scalar(select(ShipmentCollection).where(ShipmentCollection.tenant_id == tenant_id, ShipmentCollection.reference == reference)):
            raise LogisticsError('duplicate collection reference')
        if self.db.scalar(select(ShipmentCollection).where(ShipmentCollection.tenant_id == tenant_id, ShipmentCollection.shipment_id == shipment_id)):
            raise LogisticsError('shipment COD collection already exists')
        c = ShipmentCollection(tenant_id=tenant_id, shipment_id=shipment_id, reference=reference,
                               amount=amount, currency=currency, status='collected', collected_at=datetime.now(timezone.utc))
        self.db.add(c); self.db.flush()
        self._event(tenant_id, 'logistics.cod.collected', s.id,
                    {'reference': reference, 'amount': str(amount), 'currency': currency})
        try:
            self.db.commit(); self.db.refresh(c); return c
        except IntegrityError:
            self.db.rollback(); raise LogisticsError('duplicate COD collection')
