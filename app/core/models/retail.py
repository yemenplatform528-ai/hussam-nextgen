from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class RetailCustomer(Base):
    __tablename__ = 'retail_customers'
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False, default='individual')
    credit_limit: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'id', name='uq_retail_customer_tenant_id'),
        CheckConstraint("customer_type IN ('individual','business')", name='ck_retail_customer_type'),
        CheckConstraint('credit_limit >= 0', name='ck_retail_customer_credit_limit_nonnegative'),
    )


class RetailProductProfile(Base):
    __tablename__ = 'retail_product_profiles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sellable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'item_id', name='uq_retail_profile_tenant_item'),
        UniqueConstraint('tenant_id', 'sku', name='uq_retail_profile_tenant_sku'),
        UniqueConstraint('tenant_id', 'barcode', name='uq_retail_profile_tenant_barcode'),
    )


class RetailProductPrice(Base):
    __tablename__ = 'retail_product_prices'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id', 'item_id', 'currency', name='uq_retail_price_tenant_item_currency'),
        CheckConstraint('unit_price >= 0', name='ck_retail_price_nonnegative'),
    )


class RetailRegisterShift(Base):
    __tablename__ = 'retail_register_shifts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    register_id: Mapped[str] = mapped_column(String(120), nullable=False)
    operator_id: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    opening_cash: Mapped[object] = mapped_column(Numeric(20, 4), nullable=False)
    closing_cash: Mapped[object | None] = mapped_column(Numeric(20, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='open')
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index('ix_retail_register_one_open', 'tenant_id', 'register_id', unique=True, sqlite_where=(status == 'open')),

        CheckConstraint('opening_cash >= 0', name='ck_retail_shift_opening_cash_nonnegative'),
        CheckConstraint('closing_cash IS NULL OR closing_cash >= 0', name='ck_retail_shift_closing_cash_nonnegative'),
        CheckConstraint("status IN ('open','closed')", name='ck_retail_shift_status'),
    )
