from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class Shipment(Base):
    __tablename__ = 'shipments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('sales_orders.id', ondelete='RESTRICT'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    origin_warehouse_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    carrier: Mapped[str] = mapped_column(String(120), nullable=False)
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='ready')
    cod_amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'reference', name='uq_shipment_tenant_reference'),
        UniqueConstraint('tenant_id', 'tracking_number', name='uq_shipment_tenant_tracking'),
        CheckConstraint("status IN ('ready','picked_up','in_transit','out_for_delivery','delivered','failed','cancelled','returned')", name='ck_shipment_status'),
        CheckConstraint('cod_amount >= 0', name='ck_shipment_cod_nonnegative'),
    )

class ShipmentEvent(Base):
    __tablename__ = 'shipment_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'event_id', name='uq_shipment_event_tenant_event'),)

class ShipmentCollection(Base):
    __tablename__ = 'shipment_collections'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'reference', name='uq_shipment_collection_tenant_reference'),
        UniqueConstraint('tenant_id', 'shipment_id', name='uq_one_collection_per_shipment'),
        CheckConstraint('amount > 0', name='ck_shipment_collection_positive_amount'),
        CheckConstraint("status IN ('pending','collected','failed','cancelled')", name='ck_shipment_collection_status'),
    )


class CarrierIntegration(Base):
    __tablename__ = 'carrier_integrations'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    webhook_secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'code', name='uq_carrier_integration_tenant_code'),)


class CarrierEvent(Base):
    __tablename__ = 'carrier_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    carrier_id: Mapped[int] = mapped_column(ForeignKey('carrier_integrations.id', ondelete='CASCADE'), nullable=False, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey('shipments.id', ondelete='CASCADE'), nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id', 'carrier_id', 'external_event_id', name='uq_carrier_event_external_id'),)
