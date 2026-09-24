from decimal import Decimal
from datetime import date
import hashlib
import json
from fastapi import APIRouter, Depends, Query, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import desc, select, func
from app.api.dependencies import get_context, get_session
from app.core.models.marketplace import MarketplaceSellerProfile, MarketplaceOfferCompetition, MarketplaceCategory, MarketplaceListing, MarketplaceOrder, MarketplaceOrderLine, MarketplacePayout, MarketplaceReview, MarketplaceDispute, MarketplaceAddress, MarketplaceSellerVerification, MarketplaceReturnRequest, MarketplaceReturnLine, MarketplaceFeeRule, MarketplaceCart
from app.core.models.payments import PaymentIntent
from app.engines.marketplace import MarketplaceService, ListingInput
from app.engines.catalog import CatalogService, CatalogError, ProductInput, SKUInput, OfferInput
from app.engines.payments import PaymentProductionService
from app.engines.fulfillment import FulfillmentService, FulfillmentError

router=APIRouter(prefix='/marketplace',tags=['marketplace'])

def seller_guard(ctx):
    if ctx.role not in {'owner','admin'}: raise HTTPException(status_code=403, detail='seller administration requires owner or admin role')

class SellerIn(BaseModel): slug:str; display_name:str; description:str=''; seller_type:str='business'
class CategoryIn(BaseModel): slug:str; name:str; parent_id:int|None=None; market_id:int|None=None
class ListingIn(BaseModel):
    slug:str; title:str; description:str=''; listing_type:str='product'; currency:str; unit_price:Decimal=Field(ge=0)
    item_id:str|None=None; warehouse_id:str|None=None; category_id:int|None=None; stock_policy:str='managed'; market_id:int|None=None
class BuyerIn(BaseModel): display_name:str|None=None; phone:str|None=None
class AddressIn(BaseModel):
    label:str; recipient_name:str; phone:str; governorate:str; city:str; address_line:str; landmark:str|None=None
    country_code:str|None=None; market_id:int|None=None; governorate_id:int|None=None; district_id:int|None=None; locality_id:int|None=None
    neighborhood:str|None=None; street:str|None=None; building:str|None=None
    geo_lat:Decimal|None=Field(default=None,ge=-90,le=90); geo_lng:Decimal|None=Field(default=None,ge=-180,le=180)
    address_confidence:str='low'; delivery_instructions:str|None=None
class CartIn(BaseModel): listing_id:int; quantity:Decimal=Field(gt=0)
class CheckoutIn(BaseModel): shipping_address_id:int|None=None; shipping_fee:Decimal=Field(default=Decimal('0'),ge=0); shipping_quote_id:int|None=None; shipping_quote_ids:list[int]=Field(default_factory=list, max_length=50); market_id:int|None=None; payment_method_code:str|None=None
class ReviewIn(BaseModel): listing_id:int; rating:int=Field(ge=1,le=5); title:str=''; body:str=''
class DisputeIn(BaseModel): reason:str; description:str
class PaymentIn(BaseModel): provider:str=Field(min_length=1,max_length=80)
class PaymentCaptureIn(BaseModel): provider_payment_id:str=Field(min_length=1,max_length=255)
class PayoutIn(BaseModel): external_reference:str=Field(min_length=1,max_length=255)
class FeeRuleIn(BaseModel):
    name:str=Field(min_length=1,max_length=160); scope:str='global'; seller_tenant_id:int|None=None; category_id:int|None=None
    commission_bps:int=Field(ge=0,le=3000); fixed_fee:Decimal=Field(default=Decimal('0'),ge=0); currency:str|None=None; priority:int=Field(default=100,ge=0); active:bool=True
    market_id:int|None=None

class FulfillmentIn(BaseModel): method:str='seller_fulfilled'
class ShipmentForFulfillmentIn(BaseModel): carrier:str=Field(min_length=1,max_length=120); tracking_number:str|None=None
class FulfillmentTransitionIn(BaseModel): status:str; event_id:str|None=None; location:str|None=None; note:str|None=None
class PackageIn(BaseModel): reference:str=Field(min_length=1,max_length=255); weight_kg:Decimal|None=Field(default=None,gt=0); notes:str=''


class ProductCreateIn(BaseModel):
    slug:str; name:str; description:str=''; brand:str|None=None; category_id:int|None=None; market_id:int|None=None
class SKUCreateIn(BaseModel):
    sku_code:str; name:str; attributes:dict={}; item_id:str|None=None
class OfferCreateIn(BaseModel):
    currency:str; unit_price:Decimal=Field(ge=0); stock_policy:str='managed'; warehouse_id:str|None=None; shipping_fee:Decimal=Field(default=Decimal('0'),ge=0); delivery_days:int|None=Field(default=None,ge=0); market_id:int|None=None
class CatalogGroupIn(BaseModel):
    catalog_key:str=Field(min_length=1,max_length=180)

class ListingFromOfferIn(BaseModel):
    offer_id:int; slug:str; title:str|None=None; description:str|None=None; category_id:int|None=None

class CatalogBundleIn(BaseModel):
    product:ProductCreateIn; sku:SKUCreateIn; offer:OfferCreateIn; listing_slug:str; listing_title:str|None=None

@router.post('/seller/catalog/bundle', status_code=201)
def create_catalog_bundle(body:CatalogBundleIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    p,sk,of,li=CatalogService(db).create_product_bundle(ctx.tenant_id,product=ProductInput(**body.product.model_dump()),sku=SKUInput(**body.sku.model_dump()),offer=OfferInput(**body.offer.model_dump()),listing_slug=body.listing_slug,listing_title=body.listing_title)
    return {'product':{'id':p.id,'slug':p.slug,'name':p.name},'sku':{'id':sk.id,'sku_code':sk.sku_code},'offer':{'id':of.id,'currency':of.currency,'unit_price':str(of.unit_price)},'listing':{'id':li.id,'slug':li.slug,'status':li.status,'moderation_status':li.moderation_status}}

@router.post('/seller/catalog/products', status_code=201)
def create_catalog_product(body:ProductCreateIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=CatalogService(db).create_product(ctx.tenant_id,ProductInput(**body.model_dump()))
    return {'id':x.id,'slug':x.slug,'name':x.name,'description':x.description,'brand':x.brand,'category_id':x.category_id,'status':x.status}

@router.post('/seller/catalog/products/{product_id}/skus', status_code=201)
def create_catalog_sku(product_id:int,body:SKUCreateIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=CatalogService(db).create_sku(ctx.tenant_id,product_id,SKUInput(**body.model_dump()))
    return {'id':x.id,'product_id':x.product_id,'sku_code':x.sku_code,'name':x.name,'attributes':body.attributes,'item_id':x.item_id,'active':x.active}

@router.post('/seller/catalog/skus/{sku_id}/offers', status_code=201)
def create_catalog_offer(sku_id:int,body:OfferCreateIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=CatalogService(db).create_offer(ctx.tenant_id,sku_id,OfferInput(**body.model_dump()))
    return {'id':x.id,'sku_id':x.sku_id,'currency':x.currency,'unit_price':str(x.unit_price),'stock_policy':x.stock_policy,'warehouse_id':x.warehouse_id,'shipping_fee':str(x.shipping_fee),'delivery_days':x.delivery_days,'status':x.status}

@router.post('/seller/catalog/listings', status_code=201)
def create_catalog_listing(body:ListingFromOfferIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=CatalogService(db).create_listing(ctx.tenant_id,body.offer_id,slug=body.slug,category_id=body.category_id,title=body.title,description=body.description)
    return {'id':x.id,'product_id':x.product_id,'sku_id':x.sku_id,'offer_id':x.offer_id,'slug':x.slug,'title':x.title,'status':x.status,'moderation_status':x.moderation_status}

@router.get('/seller/catalog')
def seller_catalog(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); return {'items':CatalogService(db).seller_catalog(ctx.tenant_id)}


@router.post('/seller/catalog/products/{product_id}/catalog-group', status_code=201)
def assign_catalog_group(product_id:int,body:CatalogGroupIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).set_catalog_group(ctx.tenant_id,product_id,body.catalog_key)
    return {'id':x.id,'catalog_key':x.catalog_key,'title':x.title,'brand':x.brand,'status':x.status}

@router.get('/products/{product_id}/offers')
def product_offers(product_id:int,currency:str|None=None,market_id:int|None=None,db=Depends(get_session)):
    from app.core.models.catalog import MarketplaceProduct
    p=db.scalar(select(MarketplaceProduct).where(MarketplaceProduct.id==product_id))
    if not p or not p.catalog_group_id: raise HTTPException(status_code=404,detail='product catalog group not found')
    return MarketplaceService(db).offer_competition(p.catalog_group_id,currency,market_id)

@router.get('/catalog-groups/{catalog_group_id}/offers')
def catalog_group_offers(catalog_group_id:int,currency:str|None=None,market_id:int|None=None,db=Depends(get_session)):
    return MarketplaceService(db).offer_competition(catalog_group_id,currency,market_id)

@router.get('/products/{product_id}')
def public_product(product_id:int,market_id:int|None=None,db=Depends(get_session)):
    if market_id is None:
        market_id=MarketplaceService(db)._market_id(None)
    return CatalogService(db).product_view(product_id,market_id)

@router.get('/listings')
def public_listings(q:str|None=None,category_id:int|None=None,seller_slug:str|None=None,market_id:int|None=None,
                    currency:str|None=None,min_price:Decimal|None=Query(None,ge=0),
                    max_price:Decimal|None=Query(None,ge=0),in_stock:bool|None=None,
                    sort:str='relevance',limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),db=Depends(get_session)):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail='min_price cannot exceed max_price')
    items,total=MarketplaceService(db).public_listings(q=q,category_id=category_id,seller_slug=seller_slug,
        currency=currency,min_price=min_price,max_price=max_price,in_stock=in_stock,sort=sort,limit=limit,offset=offset,with_total=True,market_id=market_id)
    return {'items':items,'total':total,'limit':limit,'offset':offset,'sort':sort}

@router.get('/categories')
def categories(market_id:int|None=None,db=Depends(get_session)):
    market_id=MarketplaceService(db)._market_id(market_id)
    stmt=select(MarketplaceCategory).where(MarketplaceCategory.active.is_(True),MarketplaceCategory.market_id==market_id)
    rows=db.scalars(stmt.order_by(MarketplaceCategory.name)).all()
    return {'items':[{'id':x.id,'slug':x.slug,'name':x.name,'parent_id':x.parent_id} for x in rows]}

@router.get('/sellers')
def sellers(limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),db=Depends(get_session)):
    rows=db.scalars(select(MarketplaceSellerProfile).join(MarketplaceSellerVerification,MarketplaceSellerVerification.seller_tenant_id==MarketplaceSellerProfile.tenant_id).where(MarketplaceSellerProfile.status=='active',MarketplaceSellerVerification.status=='approved').order_by(desc(MarketplaceSellerProfile.created_at)).limit(limit).offset(offset)).all()
    return {'items':[{'tenant_id':x.tenant_id,'slug':x.slug,'display_name':x.display_name,'description':x.description,'seller_type':x.seller_type} for x in rows]}

@router.post('/seller',status_code=201)
def register_seller(body:SellerIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).register_seller(ctx.tenant_id,**body.model_dump())
    return {'tenant_id':x.tenant_id,'slug':x.slug,'display_name':x.display_name,'status':x.status}

@router.post('/seller/activate')
def activate_seller(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).activate_seller(ctx.tenant_id); return {'tenant_id':x.tenant_id,'status':x.status}

@router.post('/categories',status_code=201)
def create_category(body:CategoryIn,ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx); x=MarketplaceService(db).create_category(ctx.tenant_id,**body.model_dump()); return {'id':x.id,'slug':x.slug,'name':x.name,'parent_id':x.parent_id}

@router.post('/seller/listings',status_code=201)
def create_listing(body:ListingIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).create_listing(ctx.tenant_id,ListingInput(**body.model_dump())); return {'id':x.id,'slug':x.slug,'title':x.title,'status':x.status,'currency':x.currency,'unit_price':str(x.unit_price)}

@router.post('/seller/listings/{listing_id}/publish')
def publish_listing(listing_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).publish_listing(ctx.tenant_id,listing_id); return {'id':x.id,'status':x.status}

@router.post('/seller/listings/{listing_id}/pause')
def pause_listing(listing_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).pause_listing(ctx.tenant_id,listing_id); return {'id':x.id,'status':x.status}

@router.get('/seller/listings')
def seller_listings(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); rows=db.scalars(select(MarketplaceListing).where(MarketplaceListing.seller_tenant_id==ctx.tenant_id).order_by(desc(MarketplaceListing.id))).all(); return {'items':[{'id':x.id,'slug':x.slug,'title':x.title,'type':x.listing_type,'status':x.status,'currency':x.currency,'unit_price':str(x.unit_price),'item_id':x.item_id,'warehouse_id':x.warehouse_id} for x in rows]}

@router.post('/buyer/profile')
def buyer_profile(body:BuyerIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).ensure_buyer(ctx.user_id,body.display_name,body.phone); return {'user_id':x.user_id,'display_name':x.display_name,'phone':x.phone}

@router.post('/buyer/addresses',status_code=201)
def add_address(body:AddressIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).add_address(ctx.user_id,**body.model_dump()); return {'id':x.id,'label':x.label,'recipient_name':x.recipient_name,'phone':x.phone,'governorate':x.governorate,'city':x.city,'address_line':x.address_line,'landmark':x.landmark,'country_code':x.country_code,'market_id':x.market_id,'governorate_id':x.governorate_id,'district_id':x.district_id,'locality_id':x.locality_id,'neighborhood':x.neighborhood,'street':x.street,'building':x.building,'geo_lat':str(x.geo_lat) if x.geo_lat is not None else None,'geo_lng':str(x.geo_lng) if x.geo_lng is not None else None,'address_confidence':x.address_confidence,'delivery_instructions':x.delivery_instructions}

@router.get('/buyer/addresses')
def addresses(ctx=Depends(get_context),db=Depends(get_session)):
    rows=db.scalars(select(MarketplaceAddress).where(MarketplaceAddress.user_id==ctx.user_id,MarketplaceAddress.active.is_(True)).order_by(desc(MarketplaceAddress.id))).all(); return {'items':[{'id':x.id,'label':x.label,'recipient_name':x.recipient_name,'phone':x.phone,'governorate':x.governorate,'city':x.city,'address_line':x.address_line,'landmark':x.landmark,'country_code':x.country_code,'market_id':x.market_id,'governorate_id':x.governorate_id,'district_id':x.district_id,'locality_id':x.locality_id,'neighborhood':x.neighborhood,'street':x.street,'building':x.building,'geo_lat':str(x.geo_lat) if x.geo_lat is not None else None,'geo_lng':str(x.geo_lng) if x.geo_lng is not None else None,'address_confidence':x.address_confidence,'delivery_instructions':x.delivery_instructions} for x in rows]}

@router.get('/buyer/cart')
def get_cart(market_id:int|None=None,ctx=Depends(get_context),db=Depends(get_session)): return MarketplaceService(db).cart_view(ctx.user_id,market_id)

@router.post('/buyer/cart/items')
def add_cart(body:CartIn,ctx=Depends(get_context),db=Depends(get_session)): MarketplaceService(db).add_to_cart(ctx.user_id,body.listing_id,body.quantity); return MarketplaceService(db).cart_view(ctx.user_id)

@router.delete('/buyer/cart/items/{listing_id}')
def remove_cart(listing_id:int,ctx=Depends(get_context),db=Depends(get_session)): MarketplaceService(db).remove_from_cart(ctx.user_id,listing_id); return MarketplaceService(db).cart_view(ctx.user_id)

@router.post('/buyer/checkout',status_code=201)
def checkout(body:CheckoutIn,ctx=Depends(get_context),db=Depends(get_session),idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    request_hash = None
    if idempotency_key is not None:
        canonical = {
            'operation': 'marketplace.checkout.v1',
            'user_id': ctx.user_id,
            'body': body.model_dump(mode='json'),
        }
        request_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()
    # Resolve the same market that authoritative checkout will use, including the
    # single-active-cart fallback. This prevents the Yemen context from validating
    # one market while checkout executes against another.
    from app.core.services.yemen_checkout_context import YemenCheckoutContextService
    from app.core.models.market import MarketContext
    market_id = body.market_id
    if market_id is None:
        active_carts = db.scalars(
            select(MarketplaceCart).where(
                MarketplaceCart.buyer_user_id == ctx.user_id,
                MarketplaceCart.status == 'active',
            ).order_by(MarketplaceCart.id)
        ).all()
        if len(active_carts) == 1:
            market_id = active_carts[0].market_id
    if market_id is not None:
        market = db.scalar(select(MarketContext).where(MarketContext.id == market_id))
        if market is not None:
            try:
                context = YemenCheckoutContextService(db).build(
                    market.code,
                    user_id=ctx.user_id,
                    address_id=body.shipping_address_id,
                )
                if body.shipping_address_id is not None and context['delivery']['destination']['coverage'] not in {'available', 'active'}:
                    raise HTTPException(status_code=409, detail='delivery coverage is not available for this address')
            except ValueError as exc:
                raise HTTPException(status_code=409 if str(exc) == 'market is not active' else 404, detail=str(exc))
    orders=MarketplaceService(db).checkout(
        ctx.user_id,
        shipping_address_id=body.shipping_address_id,
        shipping_fee=body.shipping_fee,
        shipping_quote_id=body.shipping_quote_id,
        shipping_quote_ids=body.shipping_quote_ids,
        market_id=market_id,
        payment_method_code=body.payment_method_code,
        idempotency_key=idempotency_key,
        idempotency_tenant_id=ctx.tenant_id,
        idempotency_request_hash=request_hash,
    )
    return {'orders':[{'id':o.id,'reference':o.reference,'seller_tenant_id':o.seller_tenant_id,'currency':o.currency,'subtotal':str(o.subtotal),'shipping_fee':str(o.shipping_fee),'platform_fee':str(o.platform_fee),'total':str(o.total),'status':o.status} for o in orders]}

@router.post('/buyer/customer-orders/{customer_order_id}/payment-session',status_code=201)
def create_payment_session(customer_order_id:int,body:PaymentIn,ctx=Depends(get_context),db=Depends(get_session)):
    p=MarketplaceService(db).create_payment_session(ctx.user_id,customer_order_id,body.provider)
    return {'id':p.id,'reference':p.reference,'provider':p.provider,'amount':str(p.amount),'currency':p.currency,'status':p.status}

@router.post('/buyer/customer-orders/{customer_order_id}/payment-session/capture')
def capture_payment_session(customer_order_id:int,body:PaymentCaptureIn,ctx=Depends(get_context),db=Depends(get_session)):
    p=MarketplaceService(db).capture_payment_session(ctx.user_id,customer_order_id,body.provider_payment_id)
    return {'id':p.id,'reference':p.reference,'provider':p.provider,'amount':str(p.amount),'currency':p.currency,'status':p.status,'provider_payment_id':p.provider_payment_id}

@router.post('/buyer/orders/{order_id}/payment-intent',status_code=201)
def create_payment(order_id:int,body:PaymentIn,ctx=Depends(get_context),db=Depends(get_session)):
    p=MarketplaceService(db).attach_payment_intent(ctx.user_id,order_id,body.provider)
    return {'reference':p.reference,'provider':p.provider,'amount':str(p.amount),'currency':p.currency,'status':p.status}

@router.get('/buyer/orders')
def buyer_orders(ctx=Depends(get_context),db=Depends(get_session)):
    rows=db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.buyer_user_id==ctx.user_id).order_by(desc(MarketplaceOrder.id))).all()
    return {'items':[{'id':x.id,'reference':x.reference,'seller_tenant_id':x.seller_tenant_id,'customer_order_id':x.customer_order_id,'currency':x.currency,'subtotal':str(x.subtotal),'shipping_fee':str(x.shipping_fee),'platform_fee':str(x.platform_fee),'total':str(x.total),'status':x.status,'payment_reference':x.payment_reference} for x in rows], 'customer_orders': MarketplaceService(db).customer_orders(ctx.user_id)}

@router.get('/buyer/customer-orders')
def buyer_customer_orders(ctx=Depends(get_context),db=Depends(get_session)):
    return {'items': MarketplaceService(db).customer_orders(ctx.user_id)}

@router.get('/buyer/customer-orders/{customer_order_id}')
def buyer_customer_order(customer_order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    return MarketplaceService(db).customer_order_view(ctx.user_id,customer_order_id)

@router.post('/buyer/orders/{order_id}/cancel')
def cancel_order(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).cancel(ctx.user_id,order_id); return {'id':x.id,'status':x.status}

@router.post('/seller/orders/{order_id}/paid')
def mark_paid(order_id:int,payment_reference:str,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).mark_paid(ctx.tenant_id,order_id,payment_reference); return {'id':x.id,'status':x.status,'payment_reference':x.payment_reference}

@router.post('/seller/orders/{order_id}/processing')
def processing(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).mark_processing(ctx.tenant_id,order_id); return {'id':x.id,'status':x.status}

@router.post('/seller/orders/{order_id}/shipped')
def shipped(order_id:int,shipment_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).mark_shipped(ctx.tenant_id,order_id,shipment_id); return {'id':x.id,'status':x.status}

@router.post('/seller/orders/{order_id}/delivered')
def delivered(order_id:int,shipment_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).mark_delivered(ctx.tenant_id,order_id,shipment_id); return {'id':x.id,'status':x.status}

@router.post('/seller/orders/{seller_order_id}/fulfillments', status_code=201)
def create_fulfillment(seller_order_id:int,body:FulfillmentIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); f=FulfillmentService(db).create(ctx.tenant_id,seller_order_id,body.method); return {'id':f.id,'seller_order_id':f.seller_order_id,'method':f.method,'status':f.status}

@router.post('/seller/fulfillments/{fulfillment_id}/transition')
def transition_fulfillment(fulfillment_id:int,body:FulfillmentTransitionIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); f=FulfillmentService(db).transition(ctx.tenant_id,fulfillment_id,body.status,body.event_id,body.location,body.note); return {'id':f.id,'status':f.status,'shipment_id':f.shipment_id}

@router.post('/seller/fulfillments/{fulfillment_id}/packages', status_code=201)
def create_package(fulfillment_id:int,body:PackageIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); p=FulfillmentService(db).create_package(ctx.tenant_id,fulfillment_id,body.reference,body.weight_kg,body.notes); return {'id':p.id,'fulfillment_id':p.fulfillment_id,'reference':p.reference,'status':p.status,'weight_kg':str(p.weight_kg) if p.weight_kg is not None else None,'notes':p.notes}

@router.post('/seller/fulfillments/{fulfillment_id}/shipment', status_code=201)
def create_fulfillment_shipment(fulfillment_id:int,body:ShipmentForFulfillmentIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); f,s=FulfillmentService(db).create_shipment(ctx.tenant_id,fulfillment_id,body.carrier,body.tracking_number); return {'fulfillment_id':f.id,'shipment':{'id':s.id,'reference':s.reference,'status':s.status,'tracking_number':s.tracking_number,'carrier':s.carrier}}

@router.get('/seller/fulfillments/{fulfillment_id}')
def seller_fulfillment(fulfillment_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); f=FulfillmentService(db)._fulfillment(ctx.tenant_id,fulfillment_id); return {'id':f.id,'seller_order_id':f.seller_order_id,'method':f.method,'status':f.status,'shipment_id':f.shipment_id,'carrier':f.carrier,'assigned_at':f.assigned_at.isoformat() if f.assigned_at else None}

@router.get('/seller/orders')
def seller_orders(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); rows=db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id==ctx.tenant_id).order_by(desc(MarketplaceOrder.id))).all(); return {'items':[{'id':x.id,'reference':x.reference,'buyer_user_id':x.buyer_user_id,'total':str(x.total),'currency':x.currency,'status':x.status} for x in rows]}

@router.post('/seller/orders/{order_id}/settlement-link')
def settlement_link(order_id:int, settlement_reference:str,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).settle_order_payment(ctx.tenant_id,order_id,settlement_reference); return {'id':x.id,'status':x.status,'payment_reference':x.payment_reference,'settlement_reference':x.settlement_reference}

@router.post('/seller/orders/{order_id}/payout-paid')
def payout_paid(order_id:int,body:PayoutIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).mark_payout_paid(ctx.tenant_id,order_id,body.external_reference); return {'id':x.id,'status':x.status,'net_amount':str(x.net_amount),'currency':x.currency}

@router.get('/seller/statement')
def seller_statement(market_id:int, currency:str, from_at:str|None=None, to_at:str|None=None, ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    from datetime import datetime, timezone
    def parse(value):
        if not value: return None
        x=datetime.fromisoformat(value.replace('Z','+00:00'))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    return MarketplaceService(db).seller_statement(ctx.tenant_id, market_id, currency, parse(from_at), parse(to_at))

@router.get('/seller/payouts')
def seller_payouts(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); rows=db.scalars(select(MarketplacePayout).where(MarketplacePayout.seller_tenant_id==ctx.tenant_id).order_by(desc(MarketplacePayout.id))).all(); return {'items':[{'id':x.id,'order_id':x.marketplace_order_id,'reference':x.reference,'gross_amount':str(x.gross_amount),'platform_fee':str(x.platform_fee),'net_amount':str(x.net_amount),'currency':x.currency,'status':x.status,'eligible_at':x.eligible_at.isoformat() if x.eligible_at else None,'paid_at':x.paid_at.isoformat() if x.paid_at else None} for x in rows]}

@router.post('/buyer/reviews',status_code=201)
def review(body:ReviewIn,order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).create_review(ctx.user_id,order_id,body.listing_id,body.rating,body.title,body.body); return {'id':x.id,'rating':x.rating,'status':x.status}

@router.post('/buyer/disputes',status_code=201)
def dispute(body:DisputeIn,order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).open_dispute(ctx.user_id,order_id,body.reason,body.description); return {'id':x.id,'order_id':x.marketplace_order_id,'status':x.status}

@router.get('/listings/{listing_id}')
def listing(listing_id:int,db=Depends(get_session)): return MarketplaceService(db)._listing_view(MarketplaceService(db)._listing(listing_id))

class ShippingRateIn(BaseModel):
    governorate:str; city:str|None=None; currency:str; fee:Decimal=Field(ge=0); market_id:int|None=None; governorate_id:int|None=None; district_id:int|None=None; locality_id:int|None=None
class ShippingQuoteIn(BaseModel):
    address_id:int; seller_tenant_id:int; currency:str
class ReturnLineIn(BaseModel):
    order_line_id:int; quantity:Decimal=Field(gt=0)
class ReturnIn(BaseModel):
    reason:str; description:str
    lines:list[ReturnLineIn]=Field(default_factory=list,max_length=100)

@router.post('/seller/verification')
def submit_verification(body:dict|None=None,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).submit_seller_verification(ctx.tenant_id,(body or {}).get('notes','')); return {'id':x.id,'status':x.status}

@router.post('/seller/shipping-rates',status_code=201)
def add_shipping_rate(body:ShippingRateIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).add_shipping_rate(ctx.tenant_id,**body.model_dump()); return {'id':x.id,'market_id':x.market_id,'governorate':x.governorate,'city':x.city,'governorate_id':x.governorate_id,'district_id':x.district_id,'locality_id':x.locality_id,'currency':x.currency,'fee':str(x.fee)}

@router.post('/buyer/shipping-quotes',status_code=201)
def shipping_quote(body:ShippingQuoteIn,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).quote_shipping(ctx.user_id,body.address_id,body.seller_tenant_id,body.currency); return {'id':x.id,'seller_tenant_id':x.seller_tenant_id,'address_id':x.address_id,'currency':x.currency,'fee':str(x.fee),'expires_at':x.expires_at.isoformat()}

@router.post('/buyer/favorites/{listing_id}',status_code=201)
def favorite(listing_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).add_favorite(ctx.user_id,listing_id); return {'id':x.id,'listing_id':x.listing_id}

@router.delete('/buyer/favorites/{listing_id}')
def unfavorite(listing_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    MarketplaceService(db).remove_favorite(ctx.user_id,listing_id); return {'status':'removed'}

@router.post('/buyer/orders/{order_id}/sync-payment')
def sync_payment(order_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    x=MarketplaceService(db).sync_payment(ctx.user_id,order_id); return {'id':x.id,'status':x.status,'payment_reference':x.payment_reference}

@router.post('/buyer/orders/{order_id}/returns',status_code=201)
def request_return(order_id:int,body:ReturnIn,ctx=Depends(get_context),db=Depends(get_session)):
    service=MarketplaceService(db)
    x=service.request_item_return(ctx.user_id,order_id,[z.model_dump() for z in body.lines],body.reason,body.description) if body.lines else service.request_return(ctx.user_id,order_id,body.reason,body.description)
    return service.return_view(ctx.user_id,x.id)


class VerificationReviewIn(BaseModel):
    seller_tenant_id:int; decision:str; notes:str=''

@router.post('/platform/seller-verifications/review')
def review_verification(body:VerificationReviewIn,ctx=Depends(get_context),db=Depends(get_session)):
    if ctx.role != 'platform_admin': raise HTTPException(status_code=403, detail='platform operator role required')
    x=MarketplaceService(db).review_seller_verification(body.seller_tenant_id,ctx.user_id,body.decision,body.notes)
    return {'id':x.id,'seller_tenant_id':x.seller_tenant_id,'status':x.status,'reviewed_at':x.reviewed_at.isoformat() if x.reviewed_at else None}

class ModerationIn(BaseModel):
    listing_id:int; decision:str; notes:str=''
class PayoutDestinationIn(BaseModel):
    provider:str=Field(min_length=1,max_length=80); external_reference:str=Field(min_length=1,max_length=255)


def platform_admin_guard(ctx):
    if ctx.role != 'platform_admin':
        raise HTTPException(status_code=403, detail='platform administrator role required')


@router.post('/admin/fee-rules', status_code=201)
def create_fee_rule(body:FeeRuleIn,ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    if body.scope not in {'global','seller','category'}: raise HTTPException(status_code=422, detail='unsupported fee rule scope')
    if body.scope=='seller' and body.seller_tenant_id is None: raise HTTPException(status_code=422, detail='seller scope requires seller_tenant_id')
    if body.scope=='category' and body.category_id is None: raise HTTPException(status_code=422, detail='category scope requires category_id')
    if body.scope=='global' and (body.seller_tenant_id is not None or body.category_id is not None): raise HTTPException(status_code=422, detail='global scope cannot have seller/category reference')
    x=MarketplaceFeeRule(market_id=MarketplaceService(db)._market_id(body.market_id),name=body.name.strip(),scope=body.scope,seller_tenant_id=body.seller_tenant_id,category_id=body.category_id,commission_bps=body.commission_bps,fixed_fee=body.fixed_fee,currency=body.currency.upper() if body.currency else None,priority=body.priority,active=body.active)
    db.add(x); db.commit(); db.refresh(x)
    return {'id':x.id,'name':x.name,'scope':x.scope,'seller_tenant_id':x.seller_tenant_id,'category_id':x.category_id,'commission_bps':x.commission_bps,'fixed_fee':str(x.fixed_fee),'currency':x.currency,'priority':x.priority,'active':x.active}

@router.get('/admin/fee-rules')
def list_fee_rules(ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    rows=db.scalars(select(MarketplaceFeeRule).order_by(MarketplaceFeeRule.priority.asc(),MarketplaceFeeRule.id.asc())).all()
    return {'items':[{'id':x.id,'name':x.name,'scope':x.scope,'seller_tenant_id':x.seller_tenant_id,'category_id':x.category_id,'commission_bps':x.commission_bps,'fixed_fee':str(x.fixed_fee),'currency':x.currency,'priority':x.priority,'active':x.active} for x in rows]}

@router.get('/seller/center')
def seller_center(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    return MarketplaceService(db).seller_center(ctx.tenant_id)

@router.get('/seller/status')
def seller_status(ctx=Depends(get_context),db=Depends(get_session)):
    seller= db.scalar(select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id==ctx.tenant_id))
    verification=db.scalar(select(MarketplaceSellerVerification).where(MarketplaceSellerVerification.seller_tenant_id==ctx.tenant_id))
    if not seller: return {'registered':False}
    return {'registered':True,'tenant_id':seller.tenant_id,'slug':seller.slug,'status':seller.status,'verification':verification.status if verification else None}

@router.get('/seller/payout-destination')
def payout_destination(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    from app.core.models.marketplace import MarketplacePayoutDestination
    x=db.scalar(select(MarketplacePayoutDestination).where(MarketplacePayoutDestination.seller_tenant_id==ctx.tenant_id))
    return {'destination':None if not x else {'provider':x.provider,'external_reference':x.external_reference,'status':x.status,'verified_at':x.verified_at.isoformat() if x.verified_at else None}}

@router.post('/seller/payout-destination',status_code=201)
def set_payout_destination(body:PayoutDestinationIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    x=MarketplaceService(db).set_payout_destination(ctx.tenant_id,body.provider,body.external_reference)
    return {'seller_tenant_id':x.seller_tenant_id,'provider':x.provider,'external_reference':x.external_reference,'status':x.status}

@router.post('/platform/payout-destinations/{seller_tenant_id}/verify')
def verify_payout_destination(seller_tenant_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    x=MarketplaceService(db).verify_payout_destination(seller_tenant_id,ctx.user_id)
    return {'seller_tenant_id':x.seller_tenant_id,'status':x.status,'verified_at':x.verified_at.isoformat() if x.verified_at else None}

@router.post('/platform/listings/moderate')
def moderate_listing(body:ModerationIn,ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    x=MarketplaceService(db).moderate_listing(body.listing_id,ctx.user_id,body.decision,body.notes)
    return {'id':x.id,'seller_tenant_id':x.seller_tenant_id,'status':x.status,'moderation_status':x.moderation_status}

@router.get('/platform/listings/pending-moderation')
def pending_moderation(ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    rows=db.scalars(select(MarketplaceListing).where(MarketplaceListing.moderation_status=='pending').order_by(desc(MarketplaceListing.id)).limit(100)).all()
    return {'items':[{'id':x.id,'seller_tenant_id':x.seller_tenant_id,'slug':x.slug,'title':x.title,'status':x.status,'moderation_status':x.moderation_status} for x in rows]}

@router.get('/platform/categories')
def platform_categories(ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    rows=db.scalars(select(MarketplaceCategory).order_by(MarketplaceCategory.id)).all()
    return {'items':[{'id':x.id,'slug':x.slug,'name':x.name,'parent_id':x.parent_id,'active':x.active} for x in rows]}

class ReturnReviewIn(BaseModel):
    decision: str
    notes: str = ''

class ReturnTransitionIn(BaseModel):
    status: str

class RefundCompleteIn(BaseModel):
    provider_refund_id: str = Field(min_length=1, max_length=255)

class DisputeResolutionIn(BaseModel):
    decision: str
    resolution: str = Field(min_length=1, max_length=4000)

@router.get('/buyer/returns')
def buyer_returns(ctx=Depends(get_context),db=Depends(get_session)):
    rows=db.scalars(select(MarketplaceReturnRequest).join(MarketplaceOrder,MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceReturnRequest.opened_by_user_id==ctx.user_id).order_by(desc(MarketplaceReturnRequest.id))).all()
    return {'items':[{'id':x.id,'order_id':x.marketplace_order_id,'reason':x.reason,'description':x.description,'status':x.status,'refund_amount':str(x.refund_amount) if x.refund_amount is not None else None,'refund_currency':x.refund_currency,'refund_reference':x.refund_reference,'created_at':x.created_at.isoformat(),'resolved_at':x.resolved_at.isoformat() if x.resolved_at else None} for x in rows]}

@router.get('/buyer/returns/{return_id}')
def buyer_return(return_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    return MarketplaceService(db).return_view(ctx.user_id,return_id)

@router.get('/buyer/disputes/{dispute_id}')
def buyer_dispute(dispute_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    return MarketplaceService(db).dispute_view(ctx.user_id,dispute_id)

@router.get('/seller/returns')
def seller_returns(ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx)
    rows=db.scalars(select(MarketplaceReturnRequest).join(MarketplaceOrder,MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceOrder.seller_tenant_id==ctx.tenant_id).order_by(desc(MarketplaceReturnRequest.id))).all()
    return {'items':[{'id':x.id,'order_id':x.marketplace_order_id,'reason':x.reason,'description':x.description,'status':x.status,'refund_amount':str(x.refund_amount) if x.refund_amount is not None else None,'refund_currency':x.refund_currency,'refund_reference':x.refund_reference,'refund_scope':x.refund_scope} for x in rows]}

@router.post('/seller/returns/{return_id}/review')
def seller_review_return(return_id:int,body:ReturnReviewIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).review_return(ctx.tenant_id,return_id,body.decision,body.notes); return {'id':x.id,'status':x.status}

@router.post('/seller/returns/{return_id}/transition')
def seller_transition_return(return_id:int,body:ReturnTransitionIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x=MarketplaceService(db).advance_return(ctx.tenant_id,return_id,body.status); return {'id':x.id,'status':x.status}

@router.post('/seller/returns/{return_id}/approve-refund')
def seller_approve_refund(return_id:int,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x,r=MarketplaceService(db).approve_refund(ctx.tenant_id,return_id); return {'return_id':x.id,'status':x.status,'refund':{'reference':r.refund_reference,'amount':str(r.amount),'currency':r.currency,'status':r.status}}

@router.post('/seller/returns/{return_id}/complete-refund')
def seller_complete_refund(return_id:int,body:RefundCompleteIn,ctx=Depends(get_context),db=Depends(get_session)):
    seller_guard(ctx); x,r=MarketplaceService(db).complete_return_refund(ctx.tenant_id,return_id,body.provider_refund_id); return {'return_id':x.id,'status':x.status,'refund_reference':r.refund_reference,'provider_refund_id':r.provider_refund_id}

@router.get('/platform/disputes')
def platform_disputes(ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx)
    rows=db.scalars(select(MarketplaceDispute).order_by(desc(MarketplaceDispute.id)).limit(200)).all()
    return {'items':[{'id':x.id,'order_id':x.marketplace_order_id,'opened_by_user_id':x.opened_by_user_id,'reason':x.reason,'description':x.description,'status':x.status,'resolution':x.resolution} for x in rows]}

@router.post('/platform/disputes/{dispute_id}/resolve')
def platform_resolve_dispute(dispute_id:int,body:DisputeResolutionIn,ctx=Depends(get_context),db=Depends(get_session)):
    platform_admin_guard(ctx); x=MarketplaceService(db).resolve_dispute(dispute_id,ctx.user_id,body.decision,body.resolution); return {'id':x.id,'status':x.status,'resolution':x.resolution}
