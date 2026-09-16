"""Explicit AI read-tool registry. Handlers are deterministic application code; no dynamic imports or model-generated execution."""
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.models.retail import RetailProductProfile, RetailCustomer, RetailRegisterShift
from app.core.models.inventory import InventoryItem, InventoryMovementRecord
from app.core.models.commerce import SalesOrder
from app.core.models.marketplace import MarketplaceSellerProfile, MarketplaceListing, MarketplaceOrder, MarketplacePayout

READ_TOOLS = {
    'platform.overview',
    'retail.overview',
    'inventory.stock',
    'sales.summary',
    'platform.business_snapshot',
    'marketplace.overview',
    'marketplace.seller_health',
}

def _retail_overview(db: Session, tenant_id: int, args: dict):
    products=db.scalar(select(func.count()).select_from(RetailProductProfile).where(RetailProductProfile.tenant_id==tenant_id)) or 0
    customers=db.scalar(select(func.count()).select_from(RetailCustomer).where(RetailCustomer.tenant_id==tenant_id,RetailCustomer.active.is_(True))) or 0
    shifts=db.scalar(select(func.count()).select_from(RetailRegisterShift).where(RetailRegisterShift.tenant_id==tenant_id,RetailRegisterShift.status=='open')) or 0
    return {'products':int(products),'active_customers':int(customers),'open_register_shifts':int(shifts)}

def _inventory_stock(db: Session, tenant_id: int, args: dict):
    rows=db.execute(select(InventoryItem.id,InventoryItem.name).where(InventoryItem.tenant_id==tenant_id).order_by(InventoryItem.id)).all()
    return {'items':[{'item_id':r.id,'name':r.name} for r in rows[:100]],'limit':100}

def _sales_summary(db: Session, tenant_id: int, args: dict):
    count=db.scalar(select(func.count()).select_from(SalesOrder).where(SalesOrder.tenant_id==tenant_id)) or 0
    return {'orders':int(count)}

def _platform_overview(db: Session, tenant_id: int, args: dict):
    return {'tenant_id':tenant_id,'retail':_retail_overview(db,tenant_id,args)}

HANDLERS={
    'platform.overview':_platform_overview,
    'retail.overview':_retail_overview,
    'inventory.stock':_inventory_stock,
    'sales.summary':_sales_summary,
}

def _business_snapshot(db: Session, tenant_id: int, args: dict):
    from app.ai.intelligence import business_snapshot
    return business_snapshot(db, tenant_id)

HANDLERS['platform.business_snapshot'] = _business_snapshot

def execute_read_tool(db: Session, tenant_id: int, tool_code: str, arguments: dict):
    if tool_code not in READ_TOOLS or tool_code not in HANDLERS:
        raise ValueError('AI read tool is not registered')
    if not isinstance(arguments,dict): raise ValueError('tool arguments must be an object')
    return HANDLERS[tool_code](db,tenant_id,arguments)


def _marketplace_overview(db: Session, tenant_id: int, args: dict):
    seller=db.scalar(select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id==tenant_id,MarketplaceSellerProfile.status=='active'))
    listings=db.scalar(select(func.count()).select_from(MarketplaceListing).where(MarketplaceListing.seller_tenant_id==tenant_id,MarketplaceListing.status=='published',MarketplaceListing.moderation_status=='approved')) or 0
    orders=db.scalar(select(func.count()).select_from(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id==tenant_id)) or 0
    payouts=db.scalar(select(func.count()).select_from(MarketplacePayout).where(MarketplacePayout.seller_tenant_id==tenant_id,MarketplacePayout.status=='eligible')) or 0
    return {'tenant_seller_active':bool(seller),'tenant_published_listings':int(listings),'tenant_orders':int(orders),'eligible_payouts':int(payouts)}

def _marketplace_seller_health(db: Session, tenant_id: int, args: dict):
    seller=db.scalar(select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id==tenant_id))
    if not seller: return {'seller_exists':False}
    pending=db.scalar(select(func.count()).select_from(MarketplaceListing).where(MarketplaceListing.seller_tenant_id==tenant_id,MarketplaceListing.moderation_status=='pending')) or 0
    return {'seller_exists':True,'seller_status':seller.status,'pending_listings':int(pending)}

HANDLERS['marketplace.overview']=_marketplace_overview
HANDLERS['marketplace.seller_health']=_marketplace_seller_health

MUTATION_TOOLS = {
    'marketplace.price.evaluate',
    'marketplace.pricing.reprice',
    'marketplace.feed.validate',
}

def execute_mutation_tool(db: Session, tenant_id: int, tool_code: str, arguments: dict):
    if tool_code not in MUTATION_TOOLS: raise ValueError('AI mutation tool is not registered')
    from app.engines.marketplace_completion import MarketplaceCompletionService
    svc=MarketplaceCompletionService(db)
    if tool_code=='marketplace.price.evaluate':
        return svc.evaluate_price(tenant_id,int(arguments['listing_id']),str(arguments.get('source','ai')))
    if tool_code=='marketplace.pricing.reprice':
        return svc.reprice_against_market(tenant_id,int(arguments['listing_id']),arguments.get('rule_id'))
    return {'accepted':True,'feed_job_id':int(arguments['feed_job_id'])}
