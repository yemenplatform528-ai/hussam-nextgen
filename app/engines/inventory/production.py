from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.contracts import StockMovement
from app.core.models.inventory import InventoryItem, Warehouse, InventoryMovementRecord, InventoryReservation
from app.core.models.governance import OutboxEvent
from app.engines.inventory.service import InventoryInvariantError

class InventoryProductionError(ValueError):
    pass

@dataclass(frozen=True)
class StockSnapshot:
    tenant_id: int
    item_id: str
    warehouse_id: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal


def _positive(q: Decimal) -> Decimal:
    q = Decimal(str(q))
    if q <= 0:
        raise InventoryProductionError('quantity must be positive')
    return q

class InventoryProductionService:
    def __init__(self, db: Session):
        self.db = db

    def create_item(self, tenant_id: int, item_id: str, name: str, unit_code: str = 'unit') -> InventoryItem:
        if not item_id or not name or not unit_code:
            raise InventoryProductionError('item id, name and unit are required')
        if self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id == tenant_id, InventoryItem.id == item_id)):
            raise InventoryProductionError('item already exists in tenant')
        item = InventoryItem(id=item_id, tenant_id=tenant_id, name=name, unit_code=unit_code, active=True)
        self.db.add(item); self.db.commit(); self.db.refresh(item); return item

    def create_warehouse(self, tenant_id: int, warehouse_id: str, name: str, allow_negative_stock: bool = False) -> Warehouse:
        if not warehouse_id or not name:
            raise InventoryProductionError('warehouse id and name are required')
        if self.db.scalar(select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.id == warehouse_id)):
            raise InventoryProductionError('warehouse already exists in tenant')
        wh = Warehouse(id=warehouse_id, tenant_id=tenant_id, name=name, allow_negative_stock=allow_negative_stock, active=True)
        self.db.add(wh); self.db.commit(); self.db.refresh(wh); return wh

    def _tenant_item(self, tenant_id, item_id):
        item = self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id == tenant_id, InventoryItem.id == item_id, InventoryItem.active.is_(True)))
        if item is None: raise InventoryProductionError('item not found in tenant')
        return item

    def _tenant_warehouse(self, tenant_id, warehouse_id):
        wh = self.db.scalar(select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.id == warehouse_id, Warehouse.active.is_(True)))
        if wh is None: raise InventoryProductionError('warehouse not found in tenant')
        return wh

    def _lock_warehouse(self, tenant_id: int, warehouse_id: str) -> Warehouse:
        # PostgreSQL uses row-level locking to serialize stock mutations per warehouse.
        # SQLite ignores FOR UPDATE, so SQLite tests remain deterministic but do not prove concurrency.
        wh = self.db.scalar(select(Warehouse).where(Warehouse.tenant_id == tenant_id, Warehouse.id == warehouse_id, Warehouse.active.is_(True)).with_for_update())
        if wh is None:
            raise InventoryProductionError('warehouse not found in tenant')
        return wh

    def _on_hand(self, tenant_id, item_id, warehouse_id):
        rows = self.db.scalars(select(InventoryMovementRecord).where(
            InventoryMovementRecord.tenant_id == tenant_id,
            InventoryMovementRecord.item_id == item_id,
            InventoryMovementRecord.warehouse_id == warehouse_id,
        )).all()
        total = Decimal('0')
        for m in rows:
            q = Decimal(str(m.quantity))
            if m.direction == 'in': total += q
            elif m.direction == 'out': total -= q
            elif m.direction == 'transfer': total -= q
        # A transfer's destination is a separate + movement created in the same transaction.
        incoming_transfers = self.db.scalars(select(InventoryMovementRecord).where(
            InventoryMovementRecord.tenant_id == tenant_id,
            InventoryMovementRecord.item_id == item_id,
            InventoryMovementRecord.destination_warehouse_id == warehouse_id,
            InventoryMovementRecord.direction == 'transfer')).all()
        total += sum((Decimal(str(m.quantity)) for m in incoming_transfers), Decimal('0'))
        return total

    def _reserved(self, tenant_id, item_id, warehouse_id):
        rows = self.db.scalars(select(InventoryReservation).where(
            InventoryReservation.tenant_id == tenant_id,
            InventoryReservation.item_id == item_id,
            InventoryReservation.warehouse_id == warehouse_id,
            InventoryReservation.status == 'active',
            (InventoryReservation.expires_at.is_(None) | (InventoryReservation.expires_at > datetime.now(timezone.utc)))
        )).all()
        return sum((Decimal(str(r.quantity)) for r in rows), Decimal('0'))

    def snapshot(self, tenant_id: int, item_id: str, warehouse_id: str) -> StockSnapshot:
        self._tenant_item(tenant_id, item_id); self._tenant_warehouse(tenant_id, warehouse_id)
        on_hand = self._on_hand(tenant_id, item_id, warehouse_id)
        reserved = self._reserved(tenant_id, item_id, warehouse_id)
        return StockSnapshot(tenant_id, item_id, warehouse_id, on_hand, reserved, on_hand - reserved)

    def _ensure_available(self, tenant_id, item_id, warehouse_id, quantity):
        wh = self._lock_warehouse(tenant_id, warehouse_id)
        available = self.snapshot(tenant_id, item_id, warehouse_id).available
        if not wh.allow_negative_stock and quantity > available:
            raise InventoryProductionError('insufficient available stock')

    def _event(self, tenant_id, event_type, aggregate_id, payload):
        from uuid import uuid4
        self.db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=event_type,
            aggregate_type='inventory_movement', aggregate_id=str(aggregate_id), payload=payload, published=False))

    def record(self, tenant_id: int, movement: StockMovement, *, actor_id: str | None = None) -> InventoryMovementRecord:
        q = _positive(movement.quantity)
        if movement.direction not in {'in','out','transfer'}:
            raise InventoryInvariantError('unsupported movement direction')
        self._tenant_item(tenant_id, movement.item_id)
        self._tenant_warehouse(tenant_id, movement.warehouse_id)
        if movement.direction == 'transfer':
            if not movement.destination_warehouse_id or movement.destination_warehouse_id == movement.warehouse_id:
                raise InventoryProductionError('transfer requires a different destination warehouse')
            self._tenant_warehouse(tenant_id, movement.destination_warehouse_id)
            self._ensure_available(tenant_id, movement.item_id, movement.warehouse_id, q)
        elif movement.direction == 'out':
            self._ensure_available(tenant_id, movement.item_id, movement.warehouse_id, q)
        if self.db.scalar(select(InventoryMovementRecord).where(InventoryMovementRecord.tenant_id == tenant_id, InventoryMovementRecord.reference == movement.reference)):
            raise InventoryProductionError('duplicate movement reference')
        try:
            r = InventoryMovementRecord(tenant_id=tenant_id, item_id=movement.item_id, warehouse_id=movement.warehouse_id,
                destination_warehouse_id=movement.destination_warehouse_id, quantity=q, direction=movement.direction, reference=movement.reference)
            self.db.add(r); self.db.flush()
            self._event(tenant_id, 'inventory.movement.recorded', r.id, {'reference': movement.reference, 'direction': movement.direction, 'quantity': str(q)})
            self.db.commit(); self.db.refresh(r); return r
        except IntegrityError:
            self.db.rollback(); raise InventoryProductionError('movement reference already exists')

    def reserve(self, tenant_id: int, item_id: str, warehouse_id: str, quantity: Decimal, reference: str, ttl_minutes: int = 30) -> InventoryReservation:
        q = _positive(quantity)
        if ttl_minutes <= 0 or ttl_minutes > 1440: raise InventoryProductionError('reservation ttl must be between 1 and 1440 minutes')
        self._tenant_item(tenant_id,item_id); self._tenant_warehouse(tenant_id,warehouse_id)
        if self.db.scalar(select(InventoryReservation).where(InventoryReservation.tenant_id==tenant_id, InventoryReservation.reference==reference)):
            raise InventoryProductionError('duplicate reservation reference')
        self._lock_warehouse(tenant_id, warehouse_id)
        self._ensure_available(tenant_id,item_id,warehouse_id,q)
        r=InventoryReservation(tenant_id=tenant_id,item_id=item_id,warehouse_id=warehouse_id,quantity=q,reference=reference,status='active',expires_at=datetime.now(timezone.utc)+timedelta(minutes=ttl_minutes))
        self.db.add(r); self.db.flush(); self._event(tenant_id,'inventory.reservation.created',r.id,{'reference':reference,'quantity':str(q)})
        self.db.commit(); self.db.refresh(r); return r

    def release(self, tenant_id: int, reservation_id: int) -> InventoryReservation:
        r=self.db.scalar(select(InventoryReservation).where(InventoryReservation.id==reservation_id,InventoryReservation.tenant_id==tenant_id,InventoryReservation.status=='active'))
        if r is None: raise InventoryProductionError('active reservation not found in tenant')
        expires_at = r.expires_at.replace(tzinfo=timezone.utc) if r.expires_at and r.expires_at.tzinfo is None else r.expires_at
        if expires_at and expires_at <= datetime.now(timezone.utc):
            r.status='expired'; self.db.commit(); raise InventoryProductionError('reservation has expired')
        r.status='released'; self._event(tenant_id,'inventory.reservation.released',r.id,{'reference':r.reference})
        self.db.commit(); return r

    def fulfill(self, tenant_id: int, reservation_id: int, movement_reference: str) -> InventoryMovementRecord:
        r=self.db.scalar(select(InventoryReservation).where(InventoryReservation.id==reservation_id,InventoryReservation.tenant_id==tenant_id,InventoryReservation.status=='active'))
        if r is None: raise InventoryProductionError('active reservation not found in tenant')
        expires_at = r.expires_at.replace(tzinfo=timezone.utc) if r.expires_at and r.expires_at.tzinfo is None else r.expires_at
        if expires_at and expires_at <= datetime.now(timezone.utc):
            r.status='expired'; self.db.commit(); raise InventoryProductionError('reservation has expired')
        self._tenant_item(tenant_id,r.item_id); self._tenant_warehouse(tenant_id,r.warehouse_id)
        if self.db.scalar(select(InventoryMovementRecord).where(InventoryMovementRecord.tenant_id==tenant_id,InventoryMovementRecord.reference==movement_reference)):
            raise InventoryProductionError('duplicate movement reference')
        snap=self.snapshot(tenant_id,r.item_id,r.warehouse_id)
        if snap.on_hand < Decimal(str(r.quantity)):
            raise InventoryProductionError('reserved stock is no longer physically available')
        m=InventoryMovementRecord(tenant_id=tenant_id,item_id=r.item_id,warehouse_id=r.warehouse_id,quantity=r.quantity,direction='out',reference=movement_reference)
        self.db.add(m); r.status='fulfilled'; self.db.flush(); self._event(tenant_id,'inventory.reservation.fulfilled',r.id,{'reference':r.reference,'movement_reference':movement_reference})
        self.db.commit(); self.db.refresh(m); return m
