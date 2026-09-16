from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(30), nullable=False, default='unit')
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('tenant_id', 'id', name='uq_inventory_item_tenant_id'),)

class Warehouse(Base):
    __tablename__ = 'warehouses'
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    allow_negative_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('tenant_id', 'id', name='uq_warehouse_tenant_id'),)

class InventoryMovementRecord(Base):
    __tablename__='inventory_movements'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    item_id: Mapped[str] = mapped_column(String(255),nullable=False,index=True)
    warehouse_id: Mapped[str] = mapped_column(String(255),nullable=False,index=True)
    destination_warehouse_id: Mapped[str | None] = mapped_column(String(255),nullable=True,index=True)
    quantity: Mapped[object] = mapped_column(Numeric(20, 4),nullable=False)
    direction: Mapped[str] = mapped_column(String(20),nullable=False)
    reference: Mapped[str] = mapped_column(String(255),nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','reference',name='uq_inventory_movement_tenant_reference'),
        CheckConstraint("quantity > 0", name='ck_inventory_movement_positive_quantity'),
        CheckConstraint("direction IN ('in','out','transfer')", name='ck_inventory_movement_direction'),
    )

class InventoryReservation(Base):
    __tablename__='inventory_reservations'
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    item_id: Mapped[str]=mapped_column(String(255),nullable=False,index=True)
    warehouse_id: Mapped[str]=mapped_column(String(255),nullable=False,index=True)
    quantity: Mapped[object]=mapped_column(Numeric(20,4),nullable=False)
    reference: Mapped[str]=mapped_column(String(255),nullable=False)
    status: Mapped[str]=mapped_column(String(20),nullable=False,default='active')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    expires_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    __table_args__=(
        UniqueConstraint('tenant_id','reference',name='uq_reservation_tenant_reference'),
        CheckConstraint("quantity > 0", name='ck_reservation_positive_quantity'),
        CheckConstraint("status IN ('active','released','fulfilled','expired')", name='ck_reservation_status'),
    )
