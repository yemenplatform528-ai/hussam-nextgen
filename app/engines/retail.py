from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.models.inventory import InventoryItem
from app.core.models.retail import RetailCustomer, RetailProductProfile, RetailProductPrice, RetailRegisterShift
from app.core.models.governance import OutboxEvent


class RetailError(ValueError):
    pass


@dataclass(frozen=True)
class RetailProductInput:
    item_id: str
    name: str
    unit_code: str = 'unit'
    sku: str = ''
    barcode: str | None = None
    category: str | None = None
    currency: str | None = None
    unit_price: Decimal | None = None


class RetailProductionService:
    """Retail vertical adapter. Inventory, commerce and finance remain authoritative in their engines."""
    def __init__(self, db: Session):
        self.db = db

    def _event(self, tenant_id: int, event_type: str, aggregate_id: str, payload: dict):
        from uuid import uuid4
        self.db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id,
                                event_type=event_type, aggregate_type='retail',
                                aggregate_id=str(aggregate_id), payload=payload, published=False))

    def create_customer(self, tenant_id: int, customer_id: str, name: str, phone: str | None = None,
                        customer_type: str = 'individual', credit_limit: Decimal = Decimal('0')) -> RetailCustomer:
        credit_limit = Decimal(str(credit_limit))
        if not customer_id or not name: raise RetailError('customer id and name are required')
        if customer_type not in {'individual', 'business'}: raise RetailError('unsupported customer type')
        if credit_limit < 0: raise RetailError('credit limit cannot be negative')
        if self.db.scalar(select(RetailCustomer).where(RetailCustomer.tenant_id == tenant_id, RetailCustomer.id == customer_id)):
            raise RetailError('customer already exists in tenant')
        x = RetailCustomer(id=customer_id, tenant_id=tenant_id, name=name, phone=phone,
                           customer_type=customer_type, credit_limit=credit_limit, active=True)
        self.db.add(x); self._event(tenant_id, 'retail.customer.created', customer_id, {'name': name})
        try:
            self.db.commit(); self.db.refresh(x); return x
        except IntegrityError:
            self.db.rollback(); raise RetailError('customer uniqueness conflict')

    def create_product(self, tenant_id: int, data: RetailProductInput) -> InventoryItem:
        if not data.item_id or not data.name or not data.sku: raise RetailError('item id, name and SKU are required')
        if self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id == tenant_id, InventoryItem.id == data.item_id)):
            raise RetailError('product already exists in tenant')
        if self.db.scalar(select(RetailProductProfile).where(RetailProductProfile.tenant_id == tenant_id, RetailProductProfile.sku == data.sku)):
            raise RetailError('SKU already exists in tenant')
        if data.unit_price is not None and Decimal(str(data.unit_price)) < 0: raise RetailError('unit price cannot be negative')
        item = InventoryItem(id=data.item_id, tenant_id=tenant_id, name=data.name, unit_code=data.unit_code or 'unit', active=True)
        profile = RetailProductProfile(tenant_id=tenant_id, item_id=data.item_id, sku=data.sku,
                                       barcode=data.barcode, category=data.category, sellable=True)
        self.db.add_all([item, profile])
        if data.currency and data.unit_price is not None:
            self.db.add(RetailProductPrice(tenant_id=tenant_id, item_id=data.item_id,
                                            currency=data.currency, unit_price=Decimal(str(data.unit_price)), active=True))
        self._event(tenant_id, 'retail.product.created', data.item_id,
                    {'sku': data.sku, 'barcode': data.barcode, 'category': data.category})
        try:
            self.db.commit(); self.db.refresh(item); return item
        except IntegrityError:
            self.db.rollback(); raise RetailError('product SKU/barcode conflict')

    def set_price(self, tenant_id: int, item_id: str, currency: str, unit_price: Decimal) -> RetailProductPrice:
        price = Decimal(str(unit_price))
        if price < 0 or not currency: raise RetailError('valid currency and non-negative price are required')
        item = self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id == tenant_id, InventoryItem.id == item_id, InventoryItem.active.is_(True)))
        if item is None: raise RetailError('product not found in tenant')
        x = self.db.scalar(select(RetailProductPrice).where(RetailProductPrice.tenant_id == tenant_id,
                                                             RetailProductPrice.item_id == item_id,
                                                             RetailProductPrice.currency == currency))
        if x is None:
            x = RetailProductPrice(tenant_id=tenant_id, item_id=item_id, currency=currency, unit_price=price, active=True)
            self.db.add(x)
        else:
            x.unit_price = price; x.active = True
        self._event(tenant_id, 'retail.product.price_changed', item_id,
                    {'currency': currency, 'unit_price': str(price)})
        try:
            self.db.commit(); self.db.refresh(x); return x
        except IntegrityError:
            self.db.rollback(); raise RetailError('price conflict')

    def open_shift(self, tenant_id: int, register_id: str, operator_id: str, currency: str,
                   opening_cash: Decimal) -> RetailRegisterShift:
        amount = Decimal(str(opening_cash))
        if not register_id or not operator_id or not currency or amount < 0: raise RetailError('invalid register shift')
        active = self.db.scalar(select(RetailRegisterShift).where(RetailRegisterShift.tenant_id == tenant_id,
                                                                  RetailRegisterShift.register_id == register_id,
                                                                  RetailRegisterShift.status == 'open'))
        if active: raise RetailError('register already has an open shift')
        x = RetailRegisterShift(tenant_id=tenant_id, register_id=register_id, operator_id=operator_id,
                                currency=currency, opening_cash=amount, status='open')
        self.db.add(x); self._event(tenant_id, 'retail.register.shift_opened', register_id,
                                    {'operator_id': operator_id, 'currency': currency, 'opening_cash': str(amount)})
        self.db.commit(); self.db.refresh(x); return x

    def close_shift(self, tenant_id: int, shift_id: int, closing_cash: Decimal) -> RetailRegisterShift:
        amount = Decimal(str(closing_cash))
        if amount < 0: raise RetailError('closing cash cannot be negative')
        x = self.db.scalar(select(RetailRegisterShift).where(RetailRegisterShift.tenant_id == tenant_id,
                                                             RetailRegisterShift.id == shift_id).with_for_update())
        if x is None: raise RetailError('shift not found in tenant')
        if x.status != 'open': raise RetailError('shift is already closed')
        x.closing_cash = amount; x.status = 'closed'; from datetime import datetime, timezone; x.closed_at = datetime.now(timezone.utc)
        self._event(tenant_id, 'retail.register.shift_closed', x.register_id,
                    {'shift_id': x.id, 'closing_cash': str(amount)})
        self.db.commit(); return x
