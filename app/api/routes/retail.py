from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from app.api.dependencies import get_context, get_session
from app.core.models.retail import RetailCustomer, RetailProductProfile, RetailProductPrice, RetailRegisterShift
from app.core.models.inventory import InventoryItem
from app.engines.retail import RetailProductionService, RetailProductInput

router = APIRouter(prefix='/retail', tags=['retail'])

class CustomerIn(BaseModel):
    id: str; name: str; phone: str | None = None
    customer_type: str = 'individual'; credit_limit: Decimal = Field(default=Decimal('0'), ge=0)
class ProductIn(BaseModel):
    item_id: str; name: str; unit_code: str = 'unit'; sku: str
    barcode: str | None = None; category: str | None = None
    currency: str | None = None; unit_price: Decimal | None = Field(default=None, ge=0)
class PriceIn(BaseModel): currency: str; unit_price: Decimal = Field(ge=0)
class ShiftIn(BaseModel): register_id: str; currency: str; opening_cash: Decimal = Field(ge=0)
class CloseShiftIn(BaseModel): closing_cash: Decimal = Field(ge=0)

@router.post('/customers', status_code=201)
def create_customer(body: CustomerIn, ctx=Depends(get_context), db=Depends(get_session)):
    x = RetailProductionService(db).create_customer(ctx.tenant_id, body.id, body.name, body.phone, body.customer_type, body.credit_limit)
    return {'id': x.id, 'name': x.name, 'phone': x.phone, 'customer_type': x.customer_type, 'credit_limit': str(x.credit_limit), 'active': x.active}

@router.get('/customers')
def customers(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = db.scalars(select(RetailCustomer).where(RetailCustomer.tenant_id == ctx.tenant_id).order_by(desc(RetailCustomer.id)).limit(limit).offset(offset)).all()
    return {'items': [{'id': x.id, 'name': x.name, 'phone': x.phone, 'customer_type': x.customer_type, 'credit_limit': str(x.credit_limit), 'active': x.active} for x in rows], 'limit': limit, 'offset': offset}

@router.post('/products', status_code=201)
def create_product(body: ProductIn, ctx=Depends(get_context), db=Depends(get_session)):
    x = RetailProductionService(db).create_product(ctx.tenant_id, RetailProductInput(**body.model_dump()))
    return {'item_id': x.id, 'name': x.name, 'unit_code': x.unit_code}

@router.get('/products')
def products(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = db.execute(select(InventoryItem, RetailProductProfile).join(RetailProductProfile, (RetailProductProfile.tenant_id == InventoryItem.tenant_id) & (RetailProductProfile.item_id == InventoryItem.id)).where(InventoryItem.tenant_id == ctx.tenant_id).order_by(desc(InventoryItem.id)).limit(limit).offset(offset)).all()
    out=[]
    for item, profile in rows:
        prices = db.scalars(select(RetailProductPrice).where(RetailProductPrice.tenant_id == ctx.tenant_id, RetailProductPrice.item_id == item.id, RetailProductPrice.active.is_(True))).all()
        out.append({'item_id': item.id, 'name': item.name, 'unit_code': item.unit_code, 'sku': profile.sku, 'barcode': profile.barcode, 'category': profile.category, 'sellable': profile.sellable,
                    'prices': [{'currency': p.currency, 'unit_price': str(p.unit_price)} for p in prices]})
    return {'items': out, 'limit': limit, 'offset': offset}

@router.put('/products/{item_id}/price')
def set_price(item_id: str, body: PriceIn, ctx=Depends(get_context), db=Depends(get_session)):
    x = RetailProductionService(db).set_price(ctx.tenant_id, item_id, body.currency, body.unit_price)
    return {'item_id': x.item_id, 'currency': x.currency, 'unit_price': str(x.unit_price), 'active': x.active}

@router.post('/registers/shifts', status_code=201)
def open_shift(body: ShiftIn, ctx=Depends(get_context), db=Depends(get_session)):
    x = RetailProductionService(db).open_shift(ctx.tenant_id, body.register_id, ctx.user_id, body.currency, body.opening_cash)
    return {'id': x.id, 'register_id': x.register_id, 'operator_id': x.operator_id, 'currency': x.currency, 'opening_cash': str(x.opening_cash), 'status': x.status}

@router.post('/registers/shifts/{shift_id}/close')
def close_shift(shift_id: int, body: CloseShiftIn, ctx=Depends(get_context), db=Depends(get_session)):
    x = RetailProductionService(db).close_shift(ctx.tenant_id, shift_id, body.closing_cash)
    return {'id': x.id, 'register_id': x.register_id, 'closing_cash': str(x.closing_cash), 'status': x.status, 'closed_at': x.closed_at.isoformat() if x.closed_at else None}

@router.get('/registers/shifts')
def shifts(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), ctx=Depends(get_context), db=Depends(get_session)):
    rows = db.scalars(select(RetailRegisterShift).where(RetailRegisterShift.tenant_id == ctx.tenant_id).order_by(desc(RetailRegisterShift.id)).limit(limit).offset(offset)).all()
    return {'items': [{'id': x.id, 'register_id': x.register_id, 'operator_id': x.operator_id, 'currency': x.currency, 'opening_cash': str(x.opening_cash), 'closing_cash': str(x.closing_cash) if x.closing_cash is not None else None, 'status': x.status} for x in rows], 'limit': limit, 'offset': offset}

@router.get('/overview')
def overview(ctx=Depends(get_context), db=Depends(get_session)):
    tenant = ctx.tenant_id
    products = db.scalar(select(__import__('sqlalchemy').func.count()).select_from(RetailProductProfile).where(RetailProductProfile.tenant_id == tenant)) or 0
    customers = db.scalar(select(__import__('sqlalchemy').func.count()).select_from(RetailCustomer).where(RetailCustomer.tenant_id == tenant, RetailCustomer.active.is_(True))) or 0
    open_shifts = db.scalar(select(__import__('sqlalchemy').func.count()).select_from(RetailRegisterShift).where(RetailRegisterShift.tenant_id == tenant, RetailRegisterShift.status == 'open')) or 0
    return {'tenant_id': tenant, 'products': int(products), 'active_customers': int(customers), 'open_register_shifts': int(open_shifts)}
