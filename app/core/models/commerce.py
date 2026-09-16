from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class SalesOrder(Base):
    __tablename__ = 'sales_orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='draft')
    total: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'reference', name='uq_sales_order_tenant_reference'),
        CheckConstraint("status IN ('draft','confirmed','cancelled','fulfilled')", name='ck_sales_order_status'),
        CheckConstraint('total >= 0', name='ck_sales_order_total_nonnegative'),
    )


class SalesOrderLine(Base):
    __tablename__ = 'sales_order_lines'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('sales_orders.id', ondelete='CASCADE'), nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False)
    line_total: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey('inventory_reservations.id'), nullable=True)
    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_sales_order_line_positive_quantity'),
        CheckConstraint('unit_price >= 0', name='ck_sales_order_line_nonnegative_price'),
        CheckConstraint('line_total >= 0', name='ck_sales_order_line_nonnegative_total'),
    )
