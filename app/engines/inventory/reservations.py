from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models import InventoryReservation, InventoryMovementRecord

class ReservationError(ValueError): pass
class InventoryReservationService:
    def __init__(self,db:Session): self.db=db
    def reserve(self,tenant_id:int,item_id:str,warehouse_id:str,quantity:Decimal,reference:str):
        if quantity<=0 or not item_id or not warehouse_id or not reference: raise ReservationError('valid item, warehouse, quantity and reference are required')
        if self.db.scalar(select(InventoryReservation).where(InventoryReservation.tenant_id==tenant_id,InventoryReservation.reference==reference)):
            raise ReservationError('duplicate reservation reference')
        movements=self.db.scalars(select(InventoryMovementRecord).where(InventoryMovementRecord.tenant_id==tenant_id,InventoryMovementRecord.item_id==item_id,InventoryMovementRecord.warehouse_id==warehouse_id)).all()
        reserved=self.db.scalars(select(InventoryReservation).where(InventoryReservation.tenant_id==tenant_id,InventoryReservation.item_id==item_id,InventoryReservation.warehouse_id==warehouse_id,InventoryReservation.status=='active')).all()
        available=sum((Decimal(str(m.quantity)) if m.direction=='in' else -Decimal(str(m.quantity)) for m in movements),Decimal('0'))-sum((Decimal(str(r.quantity)) for r in reserved),Decimal('0'))
        if quantity>available: raise ReservationError('insufficient available stock')
        r=InventoryReservation(tenant_id=tenant_id,item_id=item_id,warehouse_id=warehouse_id,quantity=quantity,reference=reference,status='active'); self.db.add(r); self.db.commit(); self.db.refresh(r); return r
    def release(self,tenant_id:int,reservation_id:int):
        r=self.db.scalar(select(InventoryReservation).where(InventoryReservation.id==reservation_id,InventoryReservation.tenant_id==tenant_id,InventoryReservation.status=='active'))
        if not r: raise ReservationError('active reservation not found')
        r.status='released'; self.db.commit(); return r
