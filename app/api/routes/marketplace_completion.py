from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.dependencies import get_context, get_session
from app.engines.marketplace_completion import MarketplaceCompletionService, MarketplaceCompletionError

router = APIRouter(prefix='/marketplace', tags=['marketplace-completion'])

def seller_guard(ctx):
    if ctx.role not in {'owner','admin'}:
        raise HTTPException(status_code=403, detail='seller administration requires owner or admin role')

class PriceEvaluateIn(BaseModel): listing_id:int; source:str='rule'
class CouponIn(BaseModel):
    code:str; kind:str; value:Decimal=Field(ge=0); starts_at:datetime; ends_at:datetime; currency:str|None=None
    minimum_subtotal:Decimal=Query(default=Decimal('0'),ge=0); max_redemptions:int|None=Field(default=None,ge=1); per_buyer_limit:int=Field(default=1,ge=1)
class CouponRedeemIn(BaseModel): coupon_code:str; marketplace_order_id:int; subtotal:Decimal=Field(ge=0); currency:str
class AdEventIn(BaseModel):
    campaign_id:int; event_type:str; listing_id:int|None=None; ad_group_id:int|None=None; buyer_user_id:str|None=None; currency:str; bid:Decimal|None=Field(default=None,ge=0); attribution_key:str|None=None; metadata:dict={}
class AdConversionIn(BaseModel): campaign_id:int; order_id:int; revenue:Decimal=Field(ge=0); listing_id:int|None=None
class CaseMessageIn(BaseModel): sender_role:str; body:str=Field(min_length=1); internal:bool=False
class HealthSnapshotIn(BaseModel): period_start:datetime; period_end:datetime
class FeedIn(BaseModel): feed_type:str; payload:dict={}
class FeedCompleteIn(BaseModel): success:bool=True; error:str|None=None
class WebhookIn(BaseModel): integration_app_id:int; event_type:str; event_id:str; payload:dict={}
class AnalyticsIn(BaseModel): period_start:datetime; period_end:datetime

@router.post('/seller/pricing-rules/evaluate')
def evaluate_price(body:PriceEvaluateIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    return MarketplaceCompletionService(db).evaluate_price(ctx.tenant_id, body.listing_id, body.source)

@router.post('/seller/coupons', status_code=201)
def create_coupon(body:CouponIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    x=MarketplaceCompletionService(db).create_coupon(ctx.tenant_id, **body.model_dump())
    return {'id':x.id,'code':x.code,'kind':x.kind,'value':str(x.value),'active':x.active}

@router.post('/buyer/coupons/redeem', status_code=201)
def redeem_coupon(body:CouponRedeemIn,ctx=Depends(get_context),db=Depends(get_session)):
    return MarketplaceCompletionService(db).redeem_coupon(ctx.user_id, body.marketplace_order_id, body.coupon_code, body.subtotal, body.currency)

@router.get('/seller/listings/{listing_id}/promotion-preview')
def promotion_preview(listing_id:int,subtotal:Decimal=Query(default=Decimal('0'),ge=0),ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    return MarketplaceCompletionService(db).preview_promotion(ctx.tenant_id, listing_id, subtotal)

@router.post('/seller/ads/events', status_code=201)
def ad_event(body:AdEventIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    return MarketplaceCompletionService(db).ad_event(ctx.tenant_id, **body.model_dump())

@router.post('/seller/ads/conversions', status_code=201)
def ad_conversion(body:AdConversionIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    x=MarketplaceCompletionService(db).attribute_ad_conversion(ctx.tenant_id, **body.model_dump())
    return {'id':x.id,'campaign_id':x.campaign_id,'order_id':x.order_id,'attributed_revenue':str(x.attributed_revenue),'model':x.attribution_model}

@router.post('/seller/cases/{case_id}/messages', status_code=201)
def case_message(case_id:int,body:CaseMessageIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceCompletionService(db).add_case_message(case_id, ctx.user_id, body.sender_role, body.body, body.internal)
    return {'id':x.id,'case_id':x.case_id,'sender_role':x.sender_role,'internal':x.internal,'created_at':x.created_at.isoformat()}

@router.post('/seller/health/snapshot', status_code=201)
def health_snapshot(body:HealthSnapshotIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    x=MarketplaceCompletionService(db).health_snapshot(ctx.tenant_id, body.period_start, body.period_end)
    return {'id':x.id,'order_count':x.order_count,'cancelled_count':x.cancelled_count,'dispute_count':x.dispute_count,'return_count':x.return_count,'defect_rate':str(x.defect_rate),'cancellation_rate':str(x.cancellation_rate),'dispute_rate':str(x.dispute_rate),'status':x.status}

@router.post('/seller/feeds', status_code=202)
def create_feed(body:FeedIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceCompletionService(db).create_feed(ctx.tenant_id, body.feed_type, body.payload)
    return {'id':x.id,'feed_type':x.feed_type,'status':x.status,'attempts':x.attempts}

@router.post('/seller/feeds/{feed_id}/complete')
def complete_feed(feed_id:int,body:FeedCompleteIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceCompletionService(db).complete_feed(ctx.tenant_id, feed_id, body.success, body.error)
    return {'id':x.id,'status':x.status,'attempts':x.attempts,'error':x.error}

@router.post('/seller/integrations/webhooks', status_code=202)
def queue_webhook(body:WebhookIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceCompletionService(db).queue_webhook(body.integration_app_id, body.event_type, body.event_id, body.payload)
    return {'id':x.id,'status':x.status,'event_type':x.event_type,'event_id':x.event_id}

@router.post('/seller/analytics/snapshot', status_code=201)
def analytics_snapshot(body:AnalyticsIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); xs=MarketplaceCompletionService(db).analytics_snapshot(ctx.tenant_id, body.period_start, body.period_end)
    return {'items':[{'id':x.id,'metric_code':x.metric_code,'value':str(x.value),'period_end':x.period_end.isoformat()} for x in xs]}
