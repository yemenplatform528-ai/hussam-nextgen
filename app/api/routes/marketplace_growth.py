from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from app.api.dependencies import get_context, get_session
from app.api.routes.marketplace import seller_guard
from app.core.models.marketplace_growth import (
    MarketplacePricingRule, MarketplacePromotion, MarketplacePromotionItem,
    MarketplaceBrand, MarketplaceBrandStore, MarketplaceAdCampaign, MarketplaceAdGroup, MarketplaceAdTarget,
    MarketplaceB2BPrice, MarketplaceBundle, MarketplaceSubscriptionOffer, MarketplaceCustomerCase,
    MarketplaceSellerHealthMetric, MarketplaceWarehouse, MarketplaceInventoryTransfer,
    MarketplacePickupPoint, MarketplaceServiceArea, MarketplaceReportJob, MarketplaceNotification,
    MarketplaceIntegrationApp,
)

router=APIRouter(prefix='/marketplace',tags=['marketplace-growth'])

def now(): return datetime.now(timezone.utc)

class PricingRuleIn(BaseModel):
    name:str; scope_json:dict={}; action_json:dict={}; min_price:Decimal|None=None; max_price:Decimal|None=None; priority:int=Field(default=100,ge=0); active:bool=True
class PromotionIn(BaseModel):
    name:str; code:str|None=None; kind:str='percentage_off'; config_json:dict={}; starts_at:datetime; ends_at:datetime; status:str='draft'; budget:Decimal|None=None
class PromotionItemIn(BaseModel): listing_id:int
class BrandIn(BaseModel): name:str; slug:str; registry_ref:str|None=None; metadata_json:dict={}
class BrandStoreIn(BaseModel): brand_id:int; slug:str; title:str; content_json:dict={}; status:str='draft'
class AdCampaignIn(BaseModel):
    name:str; kind:str='sponsored_products'; objective:str='sales'; budget_daily:Decimal=Field(default=0,ge=0); bid_strategy:str='manual'; starts_at:datetime|None=None; ends_at:datetime|None=None
class AdGroupIn(BaseModel): campaign_id:int; name:str; default_bid:Decimal=Field(default=0,ge=0)
class AdTargetIn(BaseModel): ad_group_id:int; target_type:str; target_value:str; bid:Decimal=Field(default=0,ge=0); negative:bool=False
class B2BPriceIn(BaseModel): listing_id:int; currency:str; unit_price:Decimal=Field(ge=0); min_quantity:Decimal=Field(default=1,gt=0)
class BundleIn(BaseModel): name:str; sku:str; price:Decimal=Field(ge=0); currency:str; components_json:list=[]; status:str='draft'
class SubscriptionIn(BaseModel): listing_id:int; interval_unit:str='month'; interval_count:int=Field(default=1,gt=0); discount_bps:int=Field(default=0,ge=0,le=10000)
class CaseIn(BaseModel): case_type:str; subject:str; description:str=''; priority:str='normal'; seller_tenant_id:int|None=None; order_id:int|None=None
class HealthMetricIn(BaseModel): metric_code:str; value:Decimal; target:Decimal|None=None; status:str='healthy'; period_start:datetime; period_end:datetime; details_json:dict={}
class WarehouseIn(BaseModel): code:str; name:str; warehouse_type:str='seller'; location_json:dict={}
class TransferIn(BaseModel): from_warehouse_id:int; to_warehouse_id:int; sku_id:int|None=None; quantity:Decimal=Field(gt=0); reference:str
class PickupPointIn(BaseModel): code:str; name:str; address_json:dict={}
class ServiceAreaIn(BaseModel): code:str; name:str; rules_json:dict={}
class ReportIn(BaseModel): report_type:str; parameters_json:dict={}
class NotificationIn(BaseModel): recipient_user_id:str|None=None; notification_type:str; title:str; body:str=''; payload_json:dict={}; channel:str='in_app'
class IntegrationAppIn(BaseModel): name:str; client_id:str; scopes_json:list=[]; webhook_url:str|None=None; rate_limit_per_minute:int=Field(default=60,ge=1)

@router.post('/seller/pricing-rules',status_code=201)
def pricing_rule(body:PricingRuleIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplacePricingRule(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'name':x.name,'active':x.active,'priority':x.priority}

@router.get('/seller/pricing-rules')
def pricing_rules(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); xs=db.scalars(select(MarketplacePricingRule).where(MarketplacePricingRule.seller_tenant_id==ctx.tenant_id).order_by(MarketplacePricingRule.priority,MarketplacePricingRule.id)).all(); return {'items':[{'id':x.id,'name':x.name,'scope':x.scope_json,'action':x.action_json,'min_price':str(x.min_price) if x.min_price is not None else None,'max_price':str(x.max_price) if x.max_price is not None else None,'active':x.active,'priority':x.priority} for x in xs]}

@router.post('/seller/promotions',status_code=201)
def promotion(body:PromotionIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplacePromotion(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'status':x.status,'code':x.code}

@router.post('/seller/promotions/{promotion_id}/items',status_code=201)
def promotion_item(promotion_id:int,body:PromotionItemIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); p=db.scalar(select(MarketplacePromotion).where(MarketplacePromotion.id==promotion_id,MarketplacePromotion.seller_tenant_id==ctx.tenant_id));
    if not p: raise ValueError('promotion not found')
    x=MarketplacePromotionItem(promotion_id=p.id,listing_id=body.listing_id); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'promotion_id':p.id,'listing_id':x.listing_id}

@router.post('/seller/brands',status_code=201)
def brand(body:BrandIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceBrand(owner_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'name':x.name,'slug':x.slug,'status':x.status}

@router.post('/seller/brand-stores',status_code=201)
def brand_store(body:BrandStoreIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceBrandStore(**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'brand_id':x.brand_id,'slug':x.slug,'status':x.status}

@router.post('/seller/ad-campaigns',status_code=201)
def ad_campaign(body:AdCampaignIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceAdCampaign(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'kind':x.kind,'status':x.status}

@router.post('/seller/ad-groups',status_code=201)
def ad_group(body:AdGroupIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceAdGroup(**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'campaign_id':x.campaign_id,'status':x.status}

@router.post('/seller/ad-targets',status_code=201)
def ad_target(body:AdTargetIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceAdTarget(**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'ad_group_id':x.ad_group_id,'target_type':x.target_type}

@router.post('/seller/b2b-prices',status_code=201)
def b2b_price(body:B2BPriceIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceB2BPrice(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'listing_id':x.listing_id,'unit_price':str(x.unit_price),'min_quantity':str(x.min_quantity)}

@router.post('/seller/bundles',status_code=201)
def bundle(body:BundleIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceBundle(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'sku':x.sku,'status':x.status}

@router.post('/seller/subscriptions',status_code=201)
def subscription(body:SubscriptionIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceSubscriptionOffer(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'listing_id':x.listing_id,'interval_unit':x.interval_unit,'interval_count':x.interval_count,'discount_bps':x.discount_bps}

@router.post('/buyer/cases',status_code=201)
def case(body:CaseIn,ctx=Depends(get_context),db=Depends(get_session)):
    try:
        x=MarketplaceCompletionService(db).create_customer_case(ctx.user_id, **body.model_dump())
    except MarketplaceCompletionError as exc:
        status = 404 if 'not found' in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc))
    return {'id':x.id,'status':x.status,'priority':x.priority}

@router.get('/buyer/cases')
def cases(ctx=Depends(get_context),db=Depends(get_session)):
    xs=db.scalars(select(MarketplaceCustomerCase).where(MarketplaceCustomerCase.buyer_user_id==ctx.user_id).order_by(desc(MarketplaceCustomerCase.id))).all(); return {'items':[{'id':x.id,'case_type':x.case_type,'subject':x.subject,'status':x.status,'priority':x.priority,'order_id':x.order_id} for x in xs]}

@router.post('/seller/health-metrics',status_code=201)
def health_metric(body:HealthMetricIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceSellerHealthMetric(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'metric_code':x.metric_code,'value':str(x.value),'status':x.status}

@router.get('/seller/health')
def seller_health(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); xs=db.scalars(select(MarketplaceSellerHealthMetric).where(MarketplaceSellerHealthMetric.seller_tenant_id==ctx.tenant_id).order_by(desc(MarketplaceSellerHealthMetric.period_end),MarketplaceSellerHealthMetric.id)).all(); return {'items':[{'id':x.id,'metric_code':x.metric_code,'value':str(x.value),'target':str(x.target) if x.target is not None else None,'status':x.status,'period_start':x.period_start.isoformat(),'period_end':x.period_end.isoformat()} for x in xs]}

@router.post('/seller/warehouses',status_code=201)
def warehouse(body:WarehouseIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceWarehouse(owner_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'code':x.code,'name':x.name,'status':x.status}

@router.post('/seller/inventory-transfers',status_code=201)
def transfer(body:TransferIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceInventoryTransfer(seller_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'reference':x.reference,'status':x.status}

@router.post('/seller/pickup-points',status_code=201)
def pickup(body:PickupPointIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplacePickupPoint(operator_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'code':x.code,'status':x.status}

@router.post('/seller/service-areas',status_code=201)
def service_area(body:ServiceAreaIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceServiceArea(operator_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'code':x.code,'active':x.active}

@router.post('/seller/reports',status_code=202)
def report(body:ReportIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceReportJob(tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'report_type':x.report_type,'status':x.status}

@router.post('/seller/notifications',status_code=201)
def notification(body:NotificationIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceNotification(tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'notification_type':x.notification_type,'status':x.status}

@router.post('/seller/integrations',status_code=201)
def integration(body:IntegrationAppIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceIntegrationApp(owner_tenant_id=ctx.tenant_id,**body.model_dump()); db.add(x); db.commit(); db.refresh(x); return {'id':x.id,'client_id':x.client_id,'status':x.status,'scopes':x.scopes_json}
