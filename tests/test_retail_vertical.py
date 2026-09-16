from decimal import Decimal
import pytest
from sqlalchemy import select
from app.core.persistence import make_session_factory
from app.core.models import RetailCustomer, RetailProductProfile, RetailProductPrice, RetailRegisterShift, OutboxEvent
from app.engines.identity import IdentityService
from app.engines.retail import RetailProductionService, RetailProductInput, RetailError


def setup():
    _, factory = make_session_factory()
    db = factory(); ids = IdentityService(db)
    tenant = ids.create_tenant('متجر 1'); user = ids.create_user('retail-user', 'retail@example.com'); ids.add_membership(user.id, tenant.id, 'owner')
    tenant2 = ids.create_tenant('متجر 2')
    return db, tenant, tenant2, user


def test_retail_product_customer_price_and_shift_lifecycle():
    db, tenant, _, user = setup()
    svc = RetailProductionService(db)
    item = svc.create_product(tenant.id, RetailProductInput('milk-1','حليب','bottle','SKU-M1','628001','ألبان','YER',Decimal('850')))
    assert item.id == 'milk-1'
    assert db.scalar(select(RetailProductProfile).where(RetailProductProfile.tenant_id == tenant.id, RetailProductProfile.sku == 'SKU-M1'))
    price = db.scalar(select(RetailProductPrice).where(RetailProductPrice.tenant_id == tenant.id, RetailProductPrice.item_id == 'milk-1', RetailProductPrice.currency == 'YER'))
    assert price.unit_price == Decimal('850.0000')
    customer = svc.create_customer(tenant.id,'cust-1','عميل تجريبي','777','individual',Decimal('5000'))
    assert customer.credit_limit == Decimal('5000.0000')
    shift = svc.open_shift(tenant.id,'REG-1',user.id,'YER',Decimal('10000'))
    closed = svc.close_shift(tenant.id,shift.id,Decimal('12500'))
    assert closed.status == 'closed' and closed.closing_cash == Decimal('12500.0000')
    assert db.scalar(select(OutboxEvent).where(OutboxEvent.tenant_id == tenant.id, OutboxEvent.event_type == 'retail.product.created'))
    # Historical closed shifts are allowed; only one open shift is allowed per register.
    second = svc.open_shift(tenant.id,'REG-1',user.id,'YER',Decimal('2000'))
    assert second.status == 'open'


def test_retail_tenant_isolation_and_register_invariant():
    db, tenant, tenant2, user = setup(); svc = RetailProductionService(db)
    svc.open_shift(tenant.id,'REG-1',user.id,'YER',Decimal('100'))
    with pytest.raises(RetailError, match='open shift'):
        svc.open_shift(tenant.id,'REG-1',user.id,'YER',Decimal('100'))
    svc.create_customer(tenant.id,'same','Tenant 1')
    svc.create_customer(tenant2.id,'same','Tenant 2')
    assert db.scalar(select(RetailCustomer).where(RetailCustomer.tenant_id == tenant2.id, RetailCustomer.id == 'same')).name == 'Tenant 2'

def test_retail_product_enters_shared_inventory_and_commerce_flow():
    from app.engines.inventory.production import InventoryProductionService
    from app.engines.commerce import CommerceProductionService, OrderLineInput
    db, tenant, _, _ = setup(); retail = RetailProductionService(db)
    retail.create_product(tenant.id, RetailProductInput('rice-1','أرز 10 كجم','bag','RICE-10','628002','مواد غذائية','YER',Decimal('7000')))
    inventory = InventoryProductionService(db); commerce = CommerceProductionService(db)
    inventory.create_warehouse(tenant.id, 'store', 'المتجر')
    inventory.record(tenant.id, __import__('app.core.contracts', fromlist=['StockMovement']).StockMovement('rice-1','store',Decimal('20'),'in','opening-rice'))
    order = commerce.create_draft(tenant.id,'SALE-R1','store','YER',[OrderLineInput('rice-1',Decimal('2'),Decimal('7500'))])
    commerce.confirm(tenant.id, order.id); commerce.fulfill(tenant.id, order.id)
    snap = inventory.snapshot(tenant.id,'rice-1','store')
    assert snap.on_hand == Decimal('18.0000') and snap.available == Decimal('18.0000')
