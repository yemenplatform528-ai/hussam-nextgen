from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class Supplier(Base):
    __tablename__ = 'suppliers'
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(__import__('sqlalchemy').Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('tenant_id','id',name='uq_supplier_tenant_id'),)

class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','reference',name='uq_purchase_order_tenant_reference'),
        CheckConstraint("status IN ('draft','confirmed','cancelled','partially_received','received')", name='ck_purchase_order_status'),
        CheckConstraint('total >= 0', name='ck_purchase_order_total_nonnegative'),
    )

class PurchaseOrderLine(Base):
    __tablename__ = 'purchase_order_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    unit_cost: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    received_quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    line_total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_purchase_line_positive_quantity'),
        CheckConstraint('unit_cost >= 0', name='ck_purchase_line_nonnegative_cost'),
        CheckConstraint('received_quantity >= 0', name='ck_purchase_line_nonnegative_received'),
        CheckConstraint('received_quantity <= quantity', name='ck_purchase_line_received_lte_ordered'),
        CheckConstraint('line_total >= 0', name='ck_purchase_line_nonnegative_total'),
    )

class PurchaseReceipt(Base):
    __tablename__ = 'purchase_receipts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='posted')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','reference',name='uq_purchase_receipt_tenant_reference'),
        CheckConstraint("status = 'posted'", name='ck_purchase_receipt_status'),
        CheckConstraint('total >= 0', name='ck_purchase_receipt_total_nonnegative'),
    )

class PurchaseReceiptLine(Base):
    __tablename__ = 'purchase_receipt_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey('purchase_receipts.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    purchase_order_line_id: Mapped[int] = mapped_column(ForeignKey('purchase_order_lines.id'), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    unit_cost: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    line_total: Mapped[object] = mapped_column(Numeric(20,4), nullable=False)
    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_purchase_receipt_line_positive_quantity'),
        CheckConstraint('unit_cost >= 0', name='ck_purchase_receipt_line_nonnegative_cost'),
        CheckConstraint('line_total >= 0', name='ck_purchase_receipt_line_nonnegative_total'),
        UniqueConstraint('tenant_id','purchase_order_line_id','receipt_id',name='uq_receipt_line_orderline_receipt'),
    )
