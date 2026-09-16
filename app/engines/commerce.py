from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.commerce import SalesOrder, SalesOrderLine
from app.core.models.inventory import InventoryItem, Warehouse, InventoryMovementRecord, InventoryReservation
from app.core.models.governance import OutboxEvent


class CommerceError(ValueError):
    pass


@dataclass(frozen=True)
class OrderLineInput:
    item_id: str
    quantity: Decimal
    unit_price: Decimal


def _positive(value: Decimal, label: str) -> Decimal:
    value = Decimal(str(value))
    if value <= 0:
        raise CommerceError(f'{label} must be positive')
    return value


def _nonnegative(value: Decimal, label: str) -> Decimal:
    value = Decimal(str(value))
    if value < 0:
        raise CommerceError(f'{label} must be non-negative')
    return value


class CommerceProductionService:
    """Tenant-safe sales-order lifecycle; inventory remains authoritative for stock."""
    def __init__(self, db: Session):
        self.db = db

    def _warehouse(self, tenant_id: int, warehouse_id: str, *, lock=False):
        q = select(Warehouse).where(
            Warehouse.tenant_id == tenant_id,
            Warehouse.id == warehouse_id,
            Warehouse.active.is_(True),
        )
        if lock:
            q = q.with_for_update()
        wh = self.db.scalar(q)
        if wh is None:
            raise CommerceError('warehouse not found in tenant')
        return wh

    def _item(self, tenant_id: int, item_id: str):
        item = self.db.scalar(select(InventoryItem).where(
            InventoryItem.tenant_id == tenant_id,
            InventoryItem.id == item_id,
            InventoryItem.active.is_(True),
        ))
        if item is None:
            raise CommerceError('item not found in tenant')
        return item

    def _on_hand(self, tenant_id, item_id, warehouse_id):
        rows = self.db.scalars(select(InventoryMovementRecord).where(
            InventoryMovementRecord.tenant_id == tenant_id,
            InventoryMovementRecord.item_id == item_id,
            InventoryMovementRecord.warehouse_id == warehouse_id,
        )).all()
        total = Decimal('0')
        for m in rows:
            q = Decimal(str(m.quantity))
            if m.direction in ('out', 'transfer'):
                total -= q
            else:
                total += q
        incoming = self.db.scalars(select(InventoryMovementRecord).where(
            InventoryMovementRecord.tenant_id == tenant_id,
            InventoryMovementRecord.item_id == item_id,
            InventoryMovementRecord.destination_warehouse_id == warehouse_id,
            InventoryMovementRecord.direction == 'transfer',
        )).all()
        return total + sum((Decimal(str(m.quantity)) for m in incoming), Decimal('0'))

    def _reserved(self, tenant_id, item_id, warehouse_id):
        rows = self.db.scalars(select(InventoryReservation).where(
            InventoryReservation.tenant_id == tenant_id,
            InventoryReservation.item_id == item_id,
            InventoryReservation.warehouse_id == warehouse_id,
            InventoryReservation.status == 'active',
        )).all()
        return sum((Decimal(str(r.quantity)) for r in rows), Decimal('0'))

    def _event(self, tenant_id, event_type, aggregate_id, payload):
        from uuid import uuid4
        self.db.add(OutboxEvent(
            event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type,
            aggregate_type='sales_order', aggregate_id=str(aggregate_id),
            payload=payload, published=False,
        ))

    def create_draft(self, tenant_id: int, reference: str, warehouse_id: str,
                     currency: str, lines: list[OrderLineInput], *, commit: bool = True) -> SalesOrder:
        if not reference or not currency:
            raise CommerceError('reference and currency are required')
        if not lines:
            raise CommerceError('order requires at least one line')
        self._warehouse(tenant_id, warehouse_id)
        if self.db.scalar(select(SalesOrder).where(SalesOrder.tenant_id == tenant_id, SalesOrder.reference == reference)):
            raise CommerceError('duplicate order reference')
        order = SalesOrder(tenant_id=tenant_id, reference=reference, warehouse_id=warehouse_id,
                           currency=currency, status='draft', total=Decimal('0'))
        self.db.add(order); self.db.flush()
        total = Decimal('0')
        for data in lines:
            item = self._item(tenant_id, data.item_id)
            q = _positive(data.quantity, 'quantity')
            price = _nonnegative(data.unit_price, 'unit price')
            line_total = q * price
            total += line_total
            self.db.add(SalesOrderLine(order_id=order.id, tenant_id=tenant_id,
                                       item_id=item.id, quantity=q, unit_price=price,
                                       line_total=line_total))
        order.total = total
        self._event(tenant_id, 'commerce.order.created', order.id,
                    {'reference': reference, 'status': order.status, 'total': str(total), 'currency': currency})
        if not commit:
            return order
        try:
            self.db.commit(); self.db.refresh(order); return order
        except IntegrityError:
            self.db.rollback(); raise CommerceError('duplicate order reference')

    def confirm(self, tenant_id: int, order_id: int, *, commit: bool = True) -> SalesOrder:
        order = self.db.scalar(select(SalesOrder).where(
            SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id))
        if order is None:
            raise CommerceError('order not found in tenant')
        if order.status != 'draft':
            raise CommerceError('only draft orders can be confirmed')
        wh = self._warehouse(tenant_id, order.warehouse_id, lock=True)
        lines = self.db.scalars(select(SalesOrderLine).where(
            SalesOrderLine.order_id == order.id, SalesOrderLine.tenant_id == tenant_id)).all()
        if not lines:
            raise CommerceError('order has no lines')
        needed = {}
        for line in lines:
            key = line.item_id
            needed[key] = needed.get(key, Decimal('0')) + Decimal(str(line.quantity))
        for item_id, quantity in needed.items():
            available = self._on_hand(tenant_id, item_id, wh.id) - self._reserved(tenant_id, item_id, wh.id)
            if not wh.allow_negative_stock and quantity > available:
                raise CommerceError(f'insufficient available stock for item {item_id}')
        for line in lines:
            ref = f'order:{order.id}:line:{line.id}'
            reservation = InventoryReservation(
                tenant_id=tenant_id, item_id=line.item_id, warehouse_id=wh.id,
                quantity=Decimal(str(line.quantity)), reference=ref, status='active',
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30))
            self.db.add(reservation); self.db.flush()
            line.reservation_id = reservation.id
        order.status = 'confirmed'
        self._event(tenant_id, 'commerce.order.confirmed', order.id,
                    {'reference': order.reference, 'status': order.status})
        if not commit:
            return order
        try:
            self.db.commit(); self.db.refresh(order); return order
        except IntegrityError:
            self.db.rollback(); raise CommerceError('order confirmation conflict')

    def extend_reservations(self, tenant_id: int, order_id: int, ttl_minutes: int = 1440) -> SalesOrder:
        if ttl_minutes <= 0 or ttl_minutes > 10080:
            raise CommerceError('reservation extension must be between 1 and 10080 minutes')
        order = self.db.scalar(select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id).with_for_update())
        if order is None:
            raise CommerceError('order not found in tenant')
        if order.status not in ('confirmed',):
            raise CommerceError('only confirmed orders can extend reservations')
        reservations = self.db.scalars(select(InventoryReservation).where(
            InventoryReservation.tenant_id == tenant_id,
            InventoryReservation.id.in_(select(SalesOrderLine.reservation_id).where(SalesOrderLine.order_id == order.id, SalesOrderLine.reservation_id.is_not(None))),
            InventoryReservation.status == 'active')).all()
        if not reservations:
            raise CommerceError('active reservations not found')
        expiry = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        for r in reservations: r.expires_at = expiry
        self._event(tenant_id, 'commerce.reservations.extended', order.id, {'order_id': order.id, 'expires_at': expiry.isoformat()})
        self.db.commit(); self.db.refresh(order); return order

    def cancel(self, tenant_id: int, order_id: int) -> SalesOrder:
        order = self.db.scalar(select(SalesOrder).where(SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id))
        if order is None:
            raise CommerceError('order not found in tenant')
        if order.status not in ('draft', 'confirmed'):
            raise CommerceError('order cannot be cancelled in its current status')
        if order.status == 'confirmed':
            reservations = self.db.scalars(select(InventoryReservation).where(
                InventoryReservation.tenant_id == tenant_id,
                InventoryReservation.id.in_(select(SalesOrderLine.reservation_id).where(
                    SalesOrderLine.order_id == order.id, SalesOrderLine.reservation_id.is_not(None))),
                InventoryReservation.status == 'active',
                (InventoryReservation.expires_at.is_(None) | (InventoryReservation.expires_at > datetime.now(timezone.utc)))
            )).all()
            for r in reservations:
                r.status = 'released'
        order.status = 'cancelled'
        self._event(tenant_id, 'commerce.order.cancelled', order.id,
                    {'reference': order.reference, 'status': order.status})
        self.db.commit(); return order

    def fulfill(self, tenant_id: int, order_id: int) -> SalesOrder:
        order = self.db.scalar(select(SalesOrder).where(
            SalesOrder.id == order_id, SalesOrder.tenant_id == tenant_id))
        if order is None:
            raise CommerceError('order not found in tenant')
        if order.status != 'confirmed':
            raise CommerceError('only confirmed orders can be fulfilled')
        self._warehouse(tenant_id, order.warehouse_id, lock=True)
        lines = self.db.scalars(select(SalesOrderLine).where(
            SalesOrderLine.order_id == order.id, SalesOrderLine.tenant_id == tenant_id)).all()
        for line in lines:
            if line.reservation_id is None:
                raise CommerceError('order line has no reservation')
            r = self.db.scalar(select(InventoryReservation).where(
                InventoryReservation.id == line.reservation_id,
                InventoryReservation.tenant_id == tenant_id,
                InventoryReservation.status == 'active').with_for_update())
            if r is None:
                raise CommerceError('active reservation missing')
            physical = self._on_hand(tenant_id, r.item_id, r.warehouse_id)
            if physical < Decimal(str(r.quantity)):
                raise CommerceError('reserved stock is no longer physically available')
            ref = f'order:{order.id}:line:{line.id}:fulfill'
            if self.db.scalar(select(InventoryMovementRecord).where(
                InventoryMovementRecord.tenant_id == tenant_id,
                InventoryMovementRecord.reference == ref)):
                raise CommerceError('fulfillment movement already exists')
            self.db.add(InventoryMovementRecord(
                tenant_id=tenant_id, item_id=r.item_id, warehouse_id=r.warehouse_id,
                quantity=Decimal(str(r.quantity)), direction='out', reference=ref))
            r.status = 'fulfilled'
        order.status = 'fulfilled'
        self._event(tenant_id, 'commerce.order.fulfilled', order.id,
                    {'reference': order.reference, 'status': order.status})
        self.db.commit(); return order
