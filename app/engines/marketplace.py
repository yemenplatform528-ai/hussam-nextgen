from dataclasses import dataclass
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select, func, or_, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models.core import User, Tenant, IdempotencyRecord
from app.core.models.market import MarketContext, MarketCurrency, MarketGeography, PaymentMethodCatalogEntry
import os
from app.core.models.catalog import MarketplaceCatalogGroup, MarketplaceProduct, MarketplaceSKU, MarketplaceOffer
from app.core.models.marketplace import (
    MarketplaceSellerProfile, MarketplaceCategory, MarketplaceListing,
    MarketplaceBuyerProfile, MarketplaceAddress, MarketplaceCart, MarketplaceCartItem,
    MarketplaceOrder, MarketplaceOrderLine, MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceFulfillment, MarketplacePayout, MarketplaceSellerBalanceEntry, MarketplaceReview, MarketplaceDispute,
    MarketplaceSellerVerification, MarketplaceShippingRate, MarketplaceShippingQuote, MarketplaceFavorite, MarketplaceReturnRequest, MarketplaceReturnLine, MarketplaceRefundLine, MarketplacePayoutDestination, MarketplacePaymentSession, MarketplacePaymentAllocation, MarketplaceFeeRule, MarketplaceOrderFee, MarketplaceChargeRule, MarketplaceOrderCharge, MarketplaceOfferCompetition, MarketplaceOfferCompetitionScore,
)
from app.core.models.payments import PaymentIntent, PaymentSettlement, PaymentRefund, PaymentReconciliation
from app.core.models.logistics import Shipment
from app.core.models.commerce import SalesOrder, SalesOrderLine
from app.core.models.inventory import InventoryItem, Warehouse
from app.core.models.catalog import MarketplaceProduct, MarketplaceSKU, MarketplaceOffer
from app.core.models.governance import OutboxEvent
from app.engines.commerce import CommerceProductionService, OrderLineInput
from app.core.models.marketplace_operational import MarketplaceOrderFinancialAllocation, MarketplaceDiscountAllocation

class MarketplaceError(ValueError): pass

@dataclass(frozen=True)
class ListingInput:
    slug: str
    title: str
    description: str
    listing_type: str
    currency: str
    unit_price: Decimal
    item_id: str | None = None
    warehouse_id: str | None = None
    category_id: int | None = None
    stock_policy: str = 'managed'
    market_id: int | None = None


def _money(v):
    return Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

def _positive(v, label):
    x=_money(v)
    if x <= 0: raise MarketplaceError(f'{label} must be positive')
    return x

def _nonnegative(v, label):
    x=_money(v)
    if x < 0: raise MarketplaceError(f'{label} cannot be negative')
    return x

class MarketplaceService:
    def seller_center(self, seller_tenant_id: int):
        seller = self.db.scalar(select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id == seller_tenant_id))
        if not seller:
            return {"registered": False, "actions": [], "metrics": {}}
        verification = self.db.scalar(select(MarketplaceSellerVerification).where(MarketplaceSellerVerification.seller_tenant_id == seller_tenant_id))
        listings = self.db.scalars(select(MarketplaceListing).where(MarketplaceListing.seller_tenant_id == seller_tenant_id)).all()
        orders = self.db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id == seller_tenant_id).order_by(desc(MarketplaceOrder.id))).all()
        payouts = self.db.scalars(select(MarketplacePayout).where(MarketplacePayout.seller_tenant_id == seller_tenant_id)).all()
        fulfillments = self.db.scalars(select(MarketplaceFulfillment).where(MarketplaceFulfillment.seller_tenant_id == seller_tenant_id)).all()
        returns = self.db.scalars(select(MarketplaceReturnRequest).join(MarketplaceOrder, MarketplaceReturnRequest.marketplace_order_id == MarketplaceOrder.id).where(MarketplaceOrder.seller_tenant_id == seller_tenant_id)).all()

        pending_orders = [x for x in orders if x.status in {"paid", "processing"}]
        unfulfilled = [x for x in fulfillments if x.status in {"pending", "assigned", "ready"}]
        pending_returns = [x for x in returns if x.status in {"requested", "approved", "received", "inspected", "refund_approved"}]
        draft_listings = [x for x in listings if x.status == "draft"]
        moderation_pending = [x for x in listings if x.moderation_status == "pending"]
        gross = sum((Decimal(str(x.gross_amount)) for x in payouts), Decimal("0"))
        fees = sum((Decimal(str(x.platform_fee)) for x in payouts), Decimal("0"))
        net = sum((Decimal(str(x.net_amount)) for x in payouts), Decimal("0"))
        currency = next((x.currency for x in orders if x.currency), None) or next((x.currency for x in payouts if x.currency), None)

        actions = []
        if seller.status != "active": actions.append({"key":"seller_activation","priority":"high","title":"فعّل المتجر","count":1})
        if not verification or verification.status != "approved": actions.append({"key":"verification","priority":"high","title":"أكمل/تابع التحقق","count":1})
        if draft_listings: actions.append({"key":"draft_listings","priority":"medium","title":"استكمل المنتجات المسودة","count":len(draft_listings)})
        if moderation_pending: actions.append({"key":"moderation","priority":"medium","title":"منتجات بانتظار المراجعة","count":len(moderation_pending)})
        if pending_orders: actions.append({"key":"orders","priority":"high","title":"طلبات تحتاج تجهيزًا","count":len(pending_orders)})
        if unfulfilled: actions.append({"key":"fulfillment","priority":"high","title":"عمليات تنفيذ تحتاج إجراء","count":len(unfulfilled)})
        if pending_returns: actions.append({"key":"returns","priority":"high","title":"طلبات إرجاع تحتاج مراجعة","count":len(pending_returns)})

        return {
            "registered": True,
            "seller": {"tenant_id": seller.tenant_id, "slug": seller.slug, "display_name": seller.display_name, "status": seller.status, "verification": verification.status if verification else None},
            "metrics": {
                "listings_total": len(listings), "listings_published": sum(1 for x in listings if x.status == "published"),
                "orders_total": len(orders), "orders_actionable": len(pending_orders),
                "fulfillments_total": len(fulfillments), "fulfillments_actionable": len(unfulfilled),
                "returns_actionable": len(pending_returns),
                "payouts_total": len(payouts), "gross": str(gross), "platform_fees": str(fees), "net": str(net), "currency": currency,
            },
            "actions": actions,
            "recent_orders": [{"id":x.id,"reference":x.reference,"status":x.status,"total":str(x.total),"currency":x.currency,"created_at":x.created_at.isoformat()} for x in orders[:8]],
            "recent_payouts": [{"id":x.id,"reference":x.reference,"status":x.status,"net_amount":str(x.net_amount),"currency":x.currency,"paid_at":x.paid_at.isoformat() if x.paid_at else None} for x in payouts[-8:][::-1]],
        }


    """Marketplace orchestration. Catalog facts live here; finance/inventory/commerce remain authoritative."""
    def __init__(self, db: Session): self.db=db


    def _market_id(self, requested=None):
        if requested is not None:
            market=self.db.scalar(select(MarketContext).where(MarketContext.id==requested, MarketContext.status!='retired'))
            if not market: raise MarketplaceError('market not found or retired')
            return market.id
        active=self.db.scalars(select(MarketContext).where(MarketContext.status=='active').order_by(MarketContext.id)).all()
        if len(active)==1: return active[0].id
        raise MarketplaceError('market context is required when multiple or no active markets exist')

    def _resolve_geography(self, market_id:int, *, governorate_id=None, district_id=None, locality_id=None, governorate=None, city=None):
        """Validate a shipping/address geography against the selected market.

        Structured IDs are authoritative. Legacy governorate/city text remains a
        compatibility representation only; it is resolved when an unambiguous
        geography node exists, otherwise production requires explicit IDs.
        """
        ids = {'governorate_id': governorate_id, 'district_id': district_id, 'locality_id': locality_id}
        levels = {'governorate_id':'governorate','district_id':'district','locality_id':'locality'}
        nodes = {}
        for field, value in ids.items():
            if value is None: continue
            node=self.db.scalar(select(MarketGeography).where(MarketGeography.id==value, MarketGeography.market_id==market_id, MarketGeography.status=='active'))
            if not node or node.level != levels[field]:
                raise MarketplaceError(f'{field} does not belong to market or has invalid level')
            nodes[field]=node
        if nodes.get('district_id') and nodes.get('governorate_id') and nodes['district_id'].parent_id != nodes['governorate_id'].id:
            raise MarketplaceError('district does not belong to governorate')
        if nodes.get('locality_id') and nodes.get('district_id') and nodes['locality_id'].parent_id != nodes['district_id'].id:
            raise MarketplaceError('locality does not belong to district')
        if governorate_id is None and governorate:
            candidates=self.db.scalars(select(MarketGeography).where(MarketGeography.market_id==market_id,MarketGeography.level=='governorate',MarketGeography.status=='active',MarketGeography.name==governorate.strip())).all()
            if len(candidates)==1:
                governorate_id=candidates[0].id; nodes['governorate_id']=candidates[0]
        if district_id is None and city and nodes.get('governorate_id'):
            candidates=self.db.scalars(select(MarketGeography).where(MarketGeography.market_id==market_id,MarketGeography.level=='district',MarketGeography.status=='active',MarketGeography.parent_id==nodes['governorate_id'].id,MarketGeography.name==city.strip())).all()
            if len(candidates)==1:
                district_id=candidates[0].id; nodes['district_id']=candidates[0]
        if district_id is not None and nodes.get('district_id') is None:
            node=self.db.scalar(select(MarketGeography).where(MarketGeography.id==district_id,MarketGeography.market_id==market_id,MarketGeography.status=='active'))
            if node: nodes['district_id']=node
        return governorate_id, district_id, locality_id, nodes

    def _assert_currency(self, market_id:int, currency:str):
        c=(currency or '').strip().upper()
        if not c: raise MarketplaceError('currency is required')
        if not self.db.scalar(select(MarketCurrency).where(MarketCurrency.market_id==market_id,MarketCurrency.currency==c)):
            raise MarketplaceError('currency is not enabled for market')
        return c

    def _event(self, tenant_id, typ, aggregate_type, aggregate_id, payload):
        self.db.add(OutboxEvent(event_id=str(uuid4()),tenant_id=tenant_id,event_type=typ,aggregate_type=aggregate_type,aggregate_id=str(aggregate_id),payload=payload,published=False))

    def _fee_rule(self, seller_tenant_id:int, category_ids:set[int], currency:str, market_id:int):
        currency = currency.upper()
        now = datetime.now(timezone.utc)
        configured_rules = self.db.scalars(select(MarketplaceFeeRule).where(or_(MarketplaceFeeRule.market_id==market_id,MarketplaceFeeRule.market_id.is_(None)))).all()
        def _aware(value):
            return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value
        all_rules = [r for r in configured_rules if _aware(r.effective_from) <= now and (_aware(r.effective_to) is None or _aware(r.effective_to) > now)]
        rules = [r for r in all_rules if r.active]
        candidates=[]
        for r in rules:
            if r.currency and r.currency.upper()!=currency:
                continue
            if r.market_id not in (None, market_id):
                continue
            if r.scope=='seller' and r.seller_tenant_id==seller_tenant_id:
                candidates.append((0,r))
            elif r.scope=='category' and r.category_id in category_ids:
                candidates.append((1,r))
            elif r.scope=='global':
                candidates.append((2,r))
        if not candidates:
            raise MarketplaceError('no active marketplace fee rule configured')
        candidates.sort(key=lambda x:(x[0],x[1].priority,x[1].id))
        return candidates[0][1]

    def marketplace_charge_preview(self, basis_amount: Decimal, currency: str, charge_type: str, market_id: int | None = None, jurisdiction_code: str | None = None):
        """Return an explicitly configured tax/regulatory charge rule; absent policy means zero, not an invented tax."""
        market_id = self._market_id(market_id); currency = self._assert_currency(market_id, currency)
        charge_type = (charge_type or '').strip().lower()
        if charge_type not in {'tax','regulatory_fee','levy'}:
            raise MarketplaceError('unsupported marketplace charge type')
        now = datetime.now(timezone.utc)
        rules = self.db.scalars(select(MarketplaceChargeRule).where(or_(MarketplaceChargeRule.market_id == market_id, MarketplaceChargeRule.market_id.is_(None)), MarketplaceChargeRule.charge_type == charge_type, MarketplaceChargeRule.active.is_(True))).all()
        def aware(v): return v.replace(tzinfo=timezone.utc) if v is not None and v.tzinfo is None else v
        candidates = [r for r in rules if aware(r.effective_from) <= now and (aware(r.effective_to) is None or aware(r.effective_to) > now) and (not r.currency or r.currency.upper() == currency) and (r.jurisdiction_code is None or r.jurisdiction_code == jurisdiction_code)]
        if not candidates:
            return None, Decimal('0.0000')
        candidates.sort(key=lambda r: (0 if r.market_id == market_id else 1, 0 if r.jurisdiction_code == jurisdiction_code else 1, r.priority, r.id))
        rule = candidates[0]
        basis = _money(basis_amount)
        amount = (basis * Decimal(rule.rate_bps) / Decimal(10000) + _money(rule.fixed_amount)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        return rule, amount

    def marketplace_fee_preview(self, seller_tenant_id:int, basis_amount:Decimal, currency:str, category_ids:set[int]|None=None, market_id:int|None=None):
        market_id=self._market_id(market_id); currency=self._assert_currency(market_id,currency)
        rule=self._fee_rule(seller_tenant_id, category_ids or set(), currency, market_id)
        basis=_money(basis_amount)
        amount=(basis*Decimal(rule.commission_bps)/Decimal(10000)+_money(rule.fixed_fee)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        return rule, amount

    def _seller(self, tenant_id, active=False):
        q=select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id==tenant_id)
        if active:
            q=q.join(MarketplaceSellerVerification,MarketplaceSellerVerification.seller_tenant_id==MarketplaceSellerProfile.tenant_id).where(MarketplaceSellerProfile.status=='active',MarketplaceSellerVerification.status=='approved')
        x=self.db.scalar(q)
        if not x: raise MarketplaceError('marketplace seller profile not found')
        return x

    def register_seller(self, tenant_id:int, slug:str, display_name:str, description:str='', seller_type:str='business'):
        if not slug or not display_name: raise MarketplaceError('seller slug and display name are required')
        tenant=self.db.scalar(select(Tenant).where(Tenant.id==tenant_id,Tenant.status=='active'))
        if not tenant: raise MarketplaceError('active tenant required')
        if self.db.scalar(select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.tenant_id==tenant_id)): raise MarketplaceError('seller profile already exists')
        if self.db.scalar(select(MarketplaceSellerProfile).where(MarketplaceSellerProfile.slug==slug)): raise MarketplaceError('seller slug already exists')
        x=MarketplaceSellerProfile(tenant_id=tenant_id,slug=slug.strip(),display_name=display_name.strip(),description=description or '',seller_type=seller_type,status='pending')
        self.db.add(x); self.db.flush()
        self.db.add(MarketplaceSellerVerification(seller_tenant_id=tenant_id,status='pending'))
        self._event(tenant_id,'marketplace.seller.registered','seller',tenant_id,{'slug':x.slug}); self.db.commit(); return x

    def activate_seller(self, tenant_id:int):
        x=self._seller(tenant_id)
        verification=self.db.scalar(select(MarketplaceSellerVerification).where(MarketplaceSellerVerification.seller_tenant_id==tenant_id))
        if not verification or verification.status!='approved': raise MarketplaceError('seller verification approval is required before activation')
        if x.status not in {'pending','suspended'}: raise MarketplaceError('seller cannot be activated from current status')
        x.status='active'; self._event(tenant_id,'marketplace.seller.activated','seller',tenant_id,{}); self.db.commit(); return x

    def create_category(self, tenant_id:int, slug:str, name:str, parent_id:int|None=None, market_id:int|None=None):
        self._seller(tenant_id); market_id=self._market_id(market_id)
        if not slug or not name: raise MarketplaceError('category slug and name are required')
        if self.db.scalar(select(MarketplaceCategory).where(MarketplaceCategory.market_id==market_id,MarketplaceCategory.slug==slug)): raise MarketplaceError('category slug already exists')
        if parent_id and not self.db.scalar(select(MarketplaceCategory).where(MarketplaceCategory.id==parent_id,MarketplaceCategory.market_id==market_id,MarketplaceCategory.active.is_(True))): raise MarketplaceError('parent category not found')
        x=MarketplaceCategory(market_id=market_id,slug=slug.strip(),name=name.strip(),parent_id=parent_id,active=True); self.db.add(x); self.db.flush(); self._event(tenant_id,'marketplace.category.created','category',x.id,{'slug':x.slug}); self.db.commit(); return x

    def submit_seller_verification(self, tenant_id:int, notes:str=''):
        self._seller(tenant_id)
        x=self.db.scalar(select(MarketplaceSellerVerification).where(MarketplaceSellerVerification.seller_tenant_id==tenant_id))
        if x and x.status=='approved': raise MarketplaceError('seller is already verified')
        if not x:
            x=MarketplaceSellerVerification(seller_tenant_id=tenant_id,status='pending',notes=notes or '')
            self.db.add(x); self.db.flush()
        else:
            x.status='pending'; x.notes=notes or ''; x.submitted_at=datetime.now(timezone.utc); x.reviewed_at=None; x.reviewer_user_id=None
        self._event(tenant_id,'marketplace.seller.verification_submitted','seller_verification',x.id if x.id else tenant_id,{})
        self.db.commit(); self.db.refresh(x); return x

    def review_seller_verification(self, seller_tenant_id:int, reviewer_user_id:str, decision:str, notes:str=''):
        if decision not in {'approved','rejected'}: raise MarketplaceError('verification decision must be approved or rejected')
        x=self.db.scalar(select(MarketplaceSellerVerification).where(MarketplaceSellerVerification.seller_tenant_id==seller_tenant_id).with_for_update())
        if not x: raise MarketplaceError('verification request not found')
        x.status=decision; x.reviewed_at=datetime.now(timezone.utc); x.reviewer_user_id=reviewer_user_id; x.notes=notes or x.notes
        if decision=='approved':
            seller=self._seller(seller_tenant_id)
            if seller.status=='pending': seller.status='active'
        self._event(seller_tenant_id,'marketplace.seller.verification_'+decision,'seller_verification',x.id,{'reviewer_user_id':reviewer_user_id})
        self.db.commit(); return x

    def set_payout_destination(self, seller_tenant_id:int, provider:str, external_reference:str, status:str='pending'):
        self._seller(seller_tenant_id,active=True)
        if status not in {'pending','verified','disabled'}: raise MarketplaceError('invalid payout destination status')
        if not provider or not external_reference: raise MarketplaceError('payout destination provider and reference are required')
        x=self.db.scalar(select(MarketplacePayoutDestination).where(MarketplacePayoutDestination.seller_tenant_id==seller_tenant_id))
        if not x:
            x=MarketplacePayoutDestination(seller_tenant_id=seller_tenant_id,provider=provider.strip(),external_reference=external_reference.strip(),status='pending')
            self.db.add(x)
        else:
            x.provider=provider.strip(); x.external_reference=external_reference.strip(); x.status=status
        if status=='verified': x.verified_at=datetime.now(timezone.utc)
        self._event(seller_tenant_id,'marketplace.payout_destination.updated','payout_destination',seller_tenant_id,{'provider':x.provider,'status':x.status})
        self.db.commit(); self.db.refresh(x); return x

    def verify_payout_destination(self, seller_tenant_id:int, reviewer_user_id:str):
        x=self.db.scalar(select(MarketplacePayoutDestination).where(MarketplacePayoutDestination.seller_tenant_id==seller_tenant_id).with_for_update())
        if not x: raise MarketplaceError('payout destination not found')
        x.status='verified'; x.verified_at=datetime.now(timezone.utc)
        self._event(seller_tenant_id,'marketplace.payout_destination.verified','payout_destination',seller_tenant_id,{'reviewer_user_id':reviewer_user_id})
        self.db.commit(); return x

    def add_shipping_rate(self, seller_tenant_id:int, governorate:str, city:str|None, currency:str, fee:Decimal, market_id:int|None=None, governorate_id:int|None=None, district_id:int|None=None, locality_id:int|None=None):
        self._seller(seller_tenant_id,active=True); market_id=self._market_id(market_id); currency=self._assert_currency(market_id,currency)
        if not governorate or not currency: raise MarketplaceError('governorate and currency are required')
        governorate_id,district_id,locality_id,nodes=self._resolve_geography(market_id,governorate_id=governorate_id,district_id=district_id,locality_id=locality_id,governorate=governorate,city=city)
        if os.getenv('ENVIRONMENT','dev')=='production' and governorate_id is None:
            raise MarketplaceError('structured governorate_id is required for production shipping rates')
        f=_nonnegative(fee,'shipping fee')
        x=MarketplaceShippingRate(market_id=market_id,seller_tenant_id=seller_tenant_id,governorate=governorate.strip(),city=city.strip() if city else None,governorate_id=governorate_id,district_id=district_id,locality_id=locality_id,currency=currency,fee=f,active=True)
        self.db.add(x); self.db.flush(); self._event(seller_tenant_id,'marketplace.shipping_rate.created','shipping_rate',x.id,{'fee':str(f),'currency':x.currency}); self.db.commit(); return x

    def quote_shipping(self,user_id:str,address_id:int,seller_tenant_id:int,currency:str):
        address=self.db.scalar(select(MarketplaceAddress).where(MarketplaceAddress.id==address_id,MarketplaceAddress.user_id==user_id,MarketplaceAddress.active.is_(True)))
        if not address: raise MarketplaceError('shipping address does not belong to buyer')
        if address.market_id is None:
            candidates=self.db.scalars(select(MarketplaceShippingRate).where(MarketplaceShippingRate.seller_tenant_id==seller_tenant_id,MarketplaceShippingRate.governorate==address.governorate,MarketplaceShippingRate.currency==currency.upper(),MarketplaceShippingRate.active.is_(True)).order_by(MarketplaceShippingRate.market_id)).all()
            markets={x.market_id for x in candidates if x.market_id is not None}
            if len(markets)==1 and os.getenv('ENVIRONMENT','dev')!='production':
                address.market_id=next(iter(markets)); self.db.flush()
            else:
                raise MarketplaceError('shipping address market is required')
        currency=self._assert_currency(address.market_id,currency)
        ag,ad,al,_=self._resolve_geography(address.market_id,governorate_id=address.governorate_id,district_id=address.district_id,locality_id=address.locality_id,governorate=address.governorate,city=address.city)
        q=select(MarketplaceShippingRate).where(MarketplaceShippingRate.market_id==address.market_id,MarketplaceShippingRate.seller_tenant_id==seller_tenant_id,MarketplaceShippingRate.currency==currency.upper(),MarketplaceShippingRate.active.is_(True))
        if ag is not None:
            q=q.where(MarketplaceShippingRate.governorate_id==ag)
            if ad is not None: q=q.where(or_(MarketplaceShippingRate.district_id==ad,MarketplaceShippingRate.district_id.is_(None)))
            if al is not None: q=q.where(or_(MarketplaceShippingRate.locality_id==al,MarketplaceShippingRate.locality_id.is_(None)))
        else:
            q=q.where(MarketplaceShippingRate.governorate==address.governorate)
        q=q.order_by(desc(MarketplaceShippingRate.locality_id),desc(MarketplaceShippingRate.district_id),desc(MarketplaceShippingRate.governorate_id),desc(MarketplaceShippingRate.id))
        rate=self.db.scalar(q)
        if not rate: raise MarketplaceError('no shipping rate for destination and currency')
        quote=MarketplaceShippingQuote(market_id=address.market_id,buyer_user_id=user_id,seller_tenant_id=seller_tenant_id,address_id=address_id,currency=currency.upper(),fee=_money(rate.fee),expires_at=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(minutes=30))
        self.db.add(quote); self.db.commit(); self.db.refresh(quote); return quote

    def add_favorite(self,user_id:str,listing_id:int):
        self.ensure_buyer(user_id); self._listing(listing_id,public=True)
        if self.db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.buyer_user_id==user_id,MarketplaceFavorite.listing_id==listing_id)): return self.db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.buyer_user_id==user_id,MarketplaceFavorite.listing_id==listing_id))
        x=MarketplaceFavorite(buyer_user_id=user_id,listing_id=listing_id); self.db.add(x); self.db.commit(); return x

    def remove_favorite(self,user_id:str,listing_id:int):
        x=self.db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.buyer_user_id==user_id,MarketplaceFavorite.listing_id==listing_id))
        if x: self.db.delete(x); self.db.commit()

    def sync_payment(self,buyer_user_id:str,order_id:int):
        o=self._order(buyer_user_id,order_id,lock=True)
        if o.status!='pending_payment': return o
        p=self.db.scalar(select(PaymentIntent).where(PaymentIntent.tenant_id==o.seller_tenant_id,PaymentIntent.reference==o.payment_reference,PaymentIntent.status=='captured')) if o.payment_reference else None
        if not p: raise MarketplaceError('captured marketplace payment not found')
        if p.currency!=o.currency or _money(p.amount)!=_money(o.total): raise MarketplaceError('payment does not match order')
        try:
            payment_metadata=json.loads(p.metadata_json or '{}')
        except (TypeError, ValueError):
            payment_metadata={}
        if payment_metadata.get('market_id') is None or int(payment_metadata['market_id']) != o.market_id:
            raise MarketplaceError('payment market does not match marketplace order')
        o.status='paid'; o.updated_at=datetime.now(timezone.utc); self._event(o.seller_tenant_id,'marketplace.order.paid','marketplace_order',o.id,{'payment_reference':p.reference,'source':'payment_sync'}); self.db.commit(); return o

    def request_return(self,buyer_user_id:str,order_id:int,reason:str,description:str):
        o=self._order(buyer_user_id,order_id,lock=True)
        if o.status not in {'delivered','completed','disputed'}: raise MarketplaceError('return is only available after delivery')
        x=MarketplaceReturnRequest(market_id=o.market_id,marketplace_order_id=o.id,opened_by_user_id=buyer_user_id,reason=reason,description=description,status='requested',refund_scope='order')
        self.db.add(x); self.db.flush()
        self._event(o.seller_tenant_id,'marketplace.return.requested','return_request',x.id,{'order_id':order_id,'reason':reason,'scope':'order'})
        self.db.commit(); self.db.refresh(x); return x

    def request_item_return(self,buyer_user_id:str,order_id:int,lines:list[dict],reason:str,description:str):
        o=self._order(buyer_user_id,order_id,lock=True)
        if o.status not in {'delivered','completed','disputed'}: raise MarketplaceError('return is only available after delivery')
        if not lines: raise MarketplaceError('at least one order line is required')
        x=MarketplaceReturnRequest(market_id=o.market_id,marketplace_order_id=o.id,opened_by_user_id=buyer_user_id,reason=reason,description=description,status='requested',refund_scope='items')
        self.db.add(x); self.db.flush()
        seen=set()
        for spec in lines:
            line_id=int(spec['order_line_id']); qty=_money(spec['quantity'])
            if line_id in seen: raise MarketplaceError('duplicate order line in return')
            seen.add(line_id)
            line=self.db.scalar(select(MarketplaceOrderLine).where(MarketplaceOrderLine.id==line_id,MarketplaceOrderLine.marketplace_order_id==o.id).with_for_update())
            if not line: raise MarketplaceError('order line does not belong to order')
            if qty <= 0 or qty > _money(line.quantity): raise MarketplaceError('return quantity exceeds ordered quantity')
            active_statuses={'requested','approved','pickup','received','inspected','refund_approved','refunded'}
            prior=sum((_money(r.quantity) for r in self.db.scalars(select(MarketplaceReturnLine).join(MarketplaceReturnRequest,MarketplaceReturnRequest.id==MarketplaceReturnLine.return_request_id).where(MarketplaceReturnRequest.marketplace_order_id==o.id,MarketplaceReturnLine.order_line_id==line_id,MarketplaceReturnLine.status.in_(active_statuses))).all()),Decimal('0'))
            if prior + qty > _money(line.quantity): raise MarketplaceError('return quantity exceeds remaining returnable quantity')
            amount=(_money(line.unit_price)*qty).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
            self.db.add(MarketplaceReturnLine(return_request_id=x.id,order_line_id=line.id,quantity=qty,unit_price=_money(line.unit_price),amount=amount,reason=reason,status='requested'))
        self._event(o.seller_tenant_id,'marketplace.return.requested','return_request',x.id,{'order_id':order_id,'reason':reason,'scope':'items','line_count':len(lines)})
        self.db.commit(); self.db.refresh(x); return x

    def return_view(self,buyer_user_id:str,return_id:int):
        x=self.db.scalar(select(MarketplaceReturnRequest).join(MarketplaceOrder,MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceReturnRequest.id==return_id,MarketplaceReturnRequest.opened_by_user_id==buyer_user_id))
        if not x: raise MarketplaceError('return request not found')
        lines=self.db.scalars(select(MarketplaceReturnLine).where(MarketplaceReturnLine.return_request_id==x.id).order_by(MarketplaceReturnLine.id)).all()
        return {'id':x.id,'order_id':x.marketplace_order_id,'reason':x.reason,'description':x.description,'status':x.status,'refund_scope':x.refund_scope,'refund_amount':str(x.refund_amount) if x.refund_amount is not None else None,'refund_currency':x.refund_currency,'refund_reference':x.refund_reference,'lines':[{'id':r.id,'order_line_id':r.order_line_id,'quantity':str(r.quantity),'unit_price':str(r.unit_price),'amount':str(r.amount),'reason':r.reason,'status':r.status} for r in lines]}

    def review_return(self, actor_tenant_id:int, return_id:int, decision:str, notes:str=''):
        x=self.db.scalar(select(MarketplaceReturnRequest).join(MarketplaceOrder, MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceReturnRequest.id==return_id, MarketplaceOrder.seller_tenant_id==actor_tenant_id).with_for_update())
        if not x: raise MarketplaceError('return request not found')
        if decision not in {'approved','rejected'}: raise MarketplaceError('return decision is invalid')
        if x.status!='requested': raise MarketplaceError('return is not awaiting review')
        x.status=decision; x.resolved_at=datetime.now(timezone.utc) if decision=='rejected' else None
        lines=self.db.scalars(select(MarketplaceReturnLine).where(MarketplaceReturnLine.return_request_id==x.id)).all()
        for line in lines: line.status='approved' if decision=='approved' else 'rejected'
        self._event(actor_tenant_id,f'marketplace.return.{decision}','return_request',x.id,{'notes':notes or ''})
        self.db.commit(); return x

    def advance_return(self, actor_tenant_id:int, return_id:int, status:str):
        x=self.db.scalar(select(MarketplaceReturnRequest).join(MarketplaceOrder, MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceReturnRequest.id==return_id, MarketplaceOrder.seller_tenant_id==actor_tenant_id).with_for_update())
        if not x: raise MarketplaceError('return request not found')
        allowed={'approved':{'pickup','cancelled'},'pickup':{'received','cancelled'},'received':{'inspected'},'inspected':{'refund_approved'},'refund_approved':{'refunded'}}
        if status not in allowed.get(x.status,set()): raise MarketplaceError('invalid return transition')
        x.status=status; x.resolved_at=datetime.now(timezone.utc) if status in {'refunded','cancelled'} else None
        lines=self.db.scalars(select(MarketplaceReturnLine).where(MarketplaceReturnLine.return_request_id==x.id)).all()
        if status=='received':
            for line in lines: line.status='received'
        elif status=='cancelled':
            for line in lines: line.status='cancelled'
        self._event(actor_tenant_id,f'marketplace.return.{status}','return_request',x.id,{})
        self.db.commit(); return x

    def approve_refund(self, actor_tenant_id:int, return_id:int):
        x=self.db.scalar(select(MarketplaceReturnRequest).join(MarketplaceOrder, MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceReturnRequest.id==return_id, MarketplaceOrder.seller_tenant_id==actor_tenant_id).with_for_update())
        if not x: raise MarketplaceError('return request not found')
        if x.status!='inspected': raise MarketplaceError('return must be inspected before refund approval')
        o=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==x.marketplace_order_id).with_for_update())
        if not o.payment_reference: raise MarketplaceError('order has no payment reference')
        if x.refund_scope=='items':
            lines=self.db.scalars(select(MarketplaceReturnLine).where(MarketplaceReturnLine.return_request_id==x.id).with_for_update()).all()
            if not lines: raise MarketplaceError('item return has no return lines')
            amount=sum((_money(r.amount) for r in lines),Decimal('0'))
        else:
            amount=_money(o.total)
            lines=[]
        if amount <= 0: raise MarketplaceError('refund amount must be positive')
        from app.engines.payments import PaymentProductionService
        ref=f'REFUND:{o.reference}:{uuid4().hex[:12].upper()}'
        r=PaymentProductionService(self.db).create_refund(actor_tenant_id,o.payment_reference,refund_reference=ref,amount=amount,currency=o.currency,reason=x.reason)
        x.refund_amount=r.amount; x.refund_currency=r.currency; x.refund_reference=r.refund_reference; x.status='refund_approved'
        if lines:
            for line in lines:
                line.status='approved'
                self.db.add(MarketplaceRefundLine(payment_refund_id=r.id,return_line_id=line.id,quantity=line.quantity,amount=line.amount,currency=o.currency))
        self._event(actor_tenant_id,'marketplace.return.refund_approved','return_request',x.id,{'refund_reference':r.refund_reference,'amount':str(r.amount),'currency':r.currency,'scope':x.refund_scope})
        self.db.commit(); return x,r

    def complete_return_refund(self, actor_tenant_id:int, return_id:int, provider_refund_id:str):
        x=self.db.scalar(select(MarketplaceReturnRequest).join(MarketplaceOrder, MarketplaceOrder.id==MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceReturnRequest.id==return_id, MarketplaceOrder.seller_tenant_id==actor_tenant_id).with_for_update())
        if not x or not x.refund_reference: raise MarketplaceError('return is not awaiting refund completion')
        from app.engines.payments import PaymentProductionService
        if x.status == 'refunded':
            r=self.db.scalar(select(PaymentRefund).where(PaymentRefund.tenant_id==actor_tenant_id, PaymentRefund.refund_reference==x.refund_reference).with_for_update())
            if not r or r.status!='succeeded': raise MarketplaceError('completed return refund is missing its succeeded refund record')
            if r.provider_refund_id != provider_refund_id: raise MarketplaceError('return refund already completed with a different provider reference')
            return x,r
        if x.status!='refund_approved': raise MarketplaceError('return is not awaiting refund completion')
        r=PaymentProductionService(self.db).complete_refund(actor_tenant_id,x.refund_reference,provider_refund_id=provider_refund_id)
        x.status='refunded'; x.resolved_at=datetime.now(timezone.utc)
        lines=self.db.scalars(select(MarketplaceReturnLine).where(MarketplaceReturnLine.return_request_id==x.id)).all()
        for line in lines: line.status='refunded'
        o=self.db.get(MarketplaceOrder,x.marketplace_order_id)
        if o:
            payment=self.db.scalar(select(PaymentIntent).where(PaymentIntent.tenant_id==o.seller_tenant_id,PaymentIntent.reference==o.payment_reference))
            o.status='refunded' if payment and payment.status=='refunded' else 'partially_refunded'
            payout=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id,MarketplacePayout.seller_tenant_id==o.seller_tenant_id).with_for_update())
            if payout and payout.status in {'held','eligible'}:
                refund_amount=_money(r.amount)
                old_net=_money(payout.net_amount)
                if refund_amount >= _money(payout.gross_amount):
                    payout.gross_amount=_money(payout.seller_funded_discount) + _money(payout.platform_fee)
                    payout.net_amount=Decimal('0')
                    payout.status='reversed'
                else:
                    payout.gross_amount=_money(payout.gross_amount)-refund_amount
                    payout.net_amount=max(Decimal('0'),_money(payout.gross_amount)-_money(payout.seller_funded_discount)-_money(payout.platform_fee))
                if payout.status=='reversed' and old_net>0 and payout.eligible_at:
                    self._balance_entry(payout,'refund_reversal',old_net,r.refund_reference)
                elif payout.eligible_at and old_net > _money(payout.net_amount):
                    self._balance_entry(payout,'refund_reversal',old_net-_money(payout.net_amount),r.refund_reference)
            elif payout and payout.status=='paid':
                # A refund after seller payout creates a recoverable seller balance debit.
                # Never debit more than the seller's original net proceeds, and make the
                # operation idempotent per refund reference.
                prior_recovery = self.db.scalars(select(MarketplaceSellerBalanceEntry).where(
                    MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
                    MarketplaceSellerBalanceEntry.entry_type == 'refund_recovery'
                )).all()
                recovered = sum((_money(e.amount) for e in prior_recovery), Decimal('0'))
                remaining_exposure = max(Decimal('0'), _money(payout.net_amount) - recovered)
                recovery_amount = min(_money(r.amount), remaining_exposure)
                if recovery_amount > 0:
                    self._balance_entry(payout, 'refund_recovery', recovery_amount, r.refund_reference)
                self._event(o.seller_tenant_id,'marketplace.payout.refund_recovery_required','payout',payout.id,{
                    'order_id':o.id,'refund_amount':str(r.amount),'recovery_amount':str(recovery_amount),
                    'currency':r.currency,'refund_reference':r.refund_reference
                })
            self._sync_customer_order(o.customer_order_id)
        self.assert_refund_invariants(o.id, r.id)
        self._event(actor_tenant_id,'marketplace.return.refunded','return_request',x.id,{'refund_reference':r.refund_reference,'provider_refund_id':provider_refund_id,'amount':str(r.amount)})
        self.db.commit(); return x,r

    def dispute_view(self, buyer_user_id:str, dispute_id:int):
        x=self.db.scalar(select(MarketplaceDispute).join(MarketplaceOrder,MarketplaceOrder.id==MarketplaceDispute.marketplace_order_id).where(MarketplaceDispute.id==dispute_id,MarketplaceOrder.buyer_user_id==buyer_user_id))
        if not x: raise MarketplaceError('dispute not found')
        return {'id':x.id,'order_id':x.marketplace_order_id,'reason':x.reason,'description':x.description,'status':x.status,'resolution':x.resolution,'created_at':x.created_at.isoformat(),'resolved_at':x.resolved_at.isoformat() if x.resolved_at else None}

    def resolve_dispute(self, dispute_id:int, reviewer_user_id:str, decision:str, resolution:str):
        if decision not in {'resolved','rejected','cancelled'}: raise MarketplaceError('dispute decision is invalid')
        x=self.db.scalar(select(MarketplaceDispute).where(MarketplaceDispute.id==dispute_id).with_for_update())
        if not x: raise MarketplaceError('dispute not found')
        if x.status not in {'open','investigating'}: raise MarketplaceError('dispute is already terminal')
        x.status=decision; x.resolution=resolution.strip(); x.resolved_at=datetime.now(timezone.utc)
        o=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==x.marketplace_order_id).with_for_update())
        if o and decision!='resolved': o.status='completed' if o.status=='disputed' else o.status
        self._event(o.seller_tenant_id if o else 0,'marketplace.dispute.resolved','dispute',x.id,{'reviewer_user_id':reviewer_user_id,'decision':decision,'resolution':resolution})
        self.db.commit(); return x

    def create_listing(self, tenant_id:int, data:ListingInput):
        seller=self._seller(tenant_id,active=True)
        market_id=self._market_id(data.market_id)
        currency=self._assert_currency(market_id,data.currency)
        if not data.slug or not data.title or not data.currency: raise MarketplaceError('listing identity fields are required')
        if data.stock_policy not in {'managed','unmanaged'}: raise MarketplaceError('unsupported stock policy')
        if self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.seller_tenant_id==tenant_id,MarketplaceListing.market_id==market_id,MarketplaceListing.slug==data.slug)): raise MarketplaceError('listing slug already exists')
        if data.listing_type not in {'product','service'}: raise MarketplaceError('unsupported listing type')
        price=_nonnegative(data.unit_price,'unit price')
        if data.listing_type=='product':
            if not data.item_id or not data.warehouse_id: raise MarketplaceError('product listing requires item and warehouse')
            if not self.db.scalar(select(InventoryItem).where(InventoryItem.tenant_id==tenant_id,InventoryItem.id==data.item_id,InventoryItem.active.is_(True))): raise MarketplaceError('product item not found in seller tenant')
            if not self.db.scalar(select(Warehouse).where(Warehouse.tenant_id==tenant_id,Warehouse.id==data.warehouse_id,Warehouse.active.is_(True))): raise MarketplaceError('product warehouse not found in seller tenant')
            if data.category_id and not self.db.scalar(select(MarketplaceCategory).where(MarketplaceCategory.id==data.category_id,MarketplaceCategory.market_id==market_id,MarketplaceCategory.active.is_(True))): raise MarketplaceError('category not found')
            product=MarketplaceProduct(market_id=market_id,seller_tenant_id=tenant_id,category_id=data.category_id,slug=data.slug.strip(),name=data.title.strip(),description=data.description or '',status='draft')
            self.db.add(product); self.db.flush()
            sku=MarketplaceSKU(product_id=product.id,sku_code=f'LEGACY-{product.id}',name=data.title.strip(),attributes_json='{}',item_id=data.item_id,active=True)
            self.db.add(sku); self.db.flush()
            offer=MarketplaceOffer(market_id=market_id,seller_tenant_id=tenant_id,sku_id=sku.id,currency=currency,unit_price=price,stock_policy=data.stock_policy,warehouse_id=data.warehouse_id,status='draft')
            self.db.add(offer); self.db.flush()
            x=MarketplaceListing(market_id=market_id,seller_tenant_id=tenant_id,product_id=product.id,sku_id=sku.id,offer_id=offer.id,item_id=data.item_id,warehouse_id=data.warehouse_id,category_id=data.category_id,slug=data.slug.strip(),title=data.title.strip(),description=data.description or '',listing_type='product',currency=offer.currency,unit_price=offer.unit_price,status='draft',stock_policy=offer.stock_policy,moderation_status='pending')
        else:
            if data.category_id and not self.db.scalar(select(MarketplaceCategory).where(MarketplaceCategory.id==data.category_id,MarketplaceCategory.market_id==market_id,MarketplaceCategory.active.is_(True))): raise MarketplaceError('category not found')
            x=MarketplaceListing(market_id=market_id,seller_tenant_id=tenant_id,category_id=data.category_id,slug=data.slug.strip(),title=data.title.strip(),description=data.description or '',listing_type='service',currency=currency,unit_price=price,status='draft',stock_policy=data.stock_policy,moderation_status='pending')
        self.db.add(x); self.db.flush(); self._event(tenant_id,'marketplace.listing.created','listing',x.id,{'title':x.title,'type':x.listing_type,'product_id':x.product_id,'sku_id':x.sku_id,'offer_id':x.offer_id}); self.db.commit(); self.db.refresh(x); return x

    def publish_listing(self, tenant_id:int, listing_id:int):
        x=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id,MarketplaceListing.seller_tenant_id==tenant_id))
        if not x: raise MarketplaceError('listing not found in seller tenant')
        self._seller(tenant_id,active=True)
        if x.status not in {'draft','paused'}: raise MarketplaceError('listing cannot be published from current status')
        if x.moderation_status!='approved': raise MarketplaceError('listing moderation approval is required before publication')
        x.status='published'; x.updated_at=datetime.now(timezone.utc)
        if x.offer_id:
            offer=self.db.get(MarketplaceOffer,x.offer_id);
            if offer: offer.status='active'; offer.updated_at=datetime.now(timezone.utc)
        if x.product_id:
            product=self.db.get(MarketplaceProduct,x.product_id);
            if product: product.status='active'; product.updated_at=datetime.now(timezone.utc)
        self._event(tenant_id,'marketplace.listing.published','listing',x.id,{'slug':x.slug}); self.db.commit(); return x

    def moderate_listing(self, listing_id:int, reviewer_user_id:str, decision:str, notes:str=''):
        if decision not in {'approved','rejected','suspended'}: raise MarketplaceError('listing moderation decision is invalid')
        x=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id).with_for_update())
        if not x: raise MarketplaceError('listing not found')
        x.moderation_status=decision
        if decision in {'rejected','suspended'} and x.status=='published': x.status='paused'
        if x.offer_id and decision in {'rejected','suspended'}:
            offer=self.db.get(MarketplaceOffer,x.offer_id)
            if offer: offer.status='paused'; offer.updated_at=datetime.now(timezone.utc)
        x.updated_at=datetime.now(timezone.utc)
        self._event(x.seller_tenant_id,'marketplace.listing.moderated','listing',x.id,{'decision':decision,'reviewer_user_id':reviewer_user_id,'notes':notes or ''})
        self.db.commit(); return x

    def pause_listing(self, tenant_id:int, listing_id:int):
        x=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id,MarketplaceListing.seller_tenant_id==tenant_id))
        if not x: raise MarketplaceError('listing not found in seller tenant')
        if x.status!='published': raise MarketplaceError('only published listings can be paused')
        x.status='paused'; x.updated_at=datetime.now(timezone.utc)
        if x.offer_id:
            offer=self.db.get(MarketplaceOffer,x.offer_id)
            if offer: offer.status='paused'; offer.updated_at=datetime.now(timezone.utc)
        self._event(tenant_id,'marketplace.listing.paused','listing',x.id,{}); self.db.commit(); return x

    def _listing(self, listing_id, public=True, market_id=None):
        q=select(MarketplaceListing).where(MarketplaceListing.id==listing_id)
        if public:
            if market_id is not None: q=q.where(MarketplaceListing.market_id==market_id)
            q=q.where(MarketplaceListing.status=='published',MarketplaceListing.moderation_status=='approved')
        x=self.db.scalar(q)
        if not x: raise MarketplaceError('published listing not found')
        return x

    def public_listings(self, *, q: str | None = None, category_id: int | None = None,
                        seller_slug: str | None = None, currency: str | None = None,
                        min_price: Decimal | None = None, max_price: Decimal | None = None,
                        in_stock: bool | None = None, sort: str = 'relevance',
                        limit: int = 50, offset: int = 0, with_total: bool = False, market_id: int | None = None):
        """Public marketplace discovery authority.

        Only published + approved offers from active, verified sellers are searchable.
        Ranking is deterministic and bounded; stock is evaluated after the DB filter so
        unavailable managed inventory can be excluded without weakening publication rules.
        """
        limit = min(max(limit, 1), 100); offset = max(offset, 0)
        if market_id is None:
            market_id=self._market_id(None)
        stmt = (select(MarketplaceListing, MarketplaceSellerProfile)
                .join(MarketplaceSellerProfile,
                      MarketplaceSellerProfile.tenant_id == MarketplaceListing.seller_tenant_id)
                .join(MarketplaceSellerVerification,
                      MarketplaceSellerVerification.seller_tenant_id == MarketplaceListing.seller_tenant_id)
                .where(MarketplaceListing.market_id == market_id,
                       MarketplaceListing.status == 'published',
                       MarketplaceListing.moderation_status == 'approved',
                       MarketplaceSellerProfile.status == 'active',
                       MarketplaceSellerVerification.status == 'approved'))
        term = (q or '').strip()
        if term:
            needle = f'%{term}%'
            stmt = stmt.where(or_(MarketplaceListing.title.ilike(needle),
                                  MarketplaceListing.description.ilike(needle),
                                  MarketplaceListing.slug.ilike(needle)))
        if category_id is not None: stmt = stmt.where(MarketplaceListing.category_id == category_id)
        if seller_slug: stmt = stmt.where(MarketplaceSellerProfile.slug == seller_slug.strip())
        if currency: stmt = stmt.where(MarketplaceListing.currency == currency.strip().upper())
        if min_price is not None: stmt = stmt.where(MarketplaceListing.unit_price >= min_price)
        if max_price is not None: stmt = stmt.where(MarketplaceListing.unit_price <= max_price)

        if sort == 'price_asc': ordering = (MarketplaceListing.unit_price.asc(), MarketplaceListing.id.desc())
        elif sort == 'price_desc': ordering = (MarketplaceListing.unit_price.desc(), MarketplaceListing.id.desc())
        elif sort == 'newest': ordering = (MarketplaceListing.created_at.desc(), MarketplaceListing.id.desc())
        elif sort == 'relevance':
            if term:
                exact = func.lower(MarketplaceListing.title) == term.lower()
                prefix = MarketplaceListing.title.ilike(f'{term}%')
                ordering = (desc(exact), desc(prefix), MarketplaceListing.updated_at.desc(), MarketplaceListing.id.desc())
            else:
                ordering = (MarketplaceListing.updated_at.desc(), MarketplaceListing.id.desc())
        else:
            raise MarketplaceError('unsupported search sort')

        rows = self.db.execute(stmt.order_by(*ordering)).all()
        items = []
        for x, seller in rows:
            view = self._listing_view(x, seller)
            if in_stock is not None:
                stock = view['stock']
                available = stock is None or Decimal(stock) > 0
                if available != in_stock: continue
            items.append(view)
        total = len(items)
        page = items[offset:offset + limit]
        return (page, total) if with_total else page

    def _stock(self, listing):
        if listing.listing_type!='product' or listing.stock_policy=='unmanaged': return None
        from app.engines.inventory.production import InventoryProductionService
        try: return InventoryProductionService(self.db).snapshot(listing.seller_tenant_id,listing.item_id,listing.warehouse_id).available
        except Exception: return Decimal('0')

    def _listing_view(self,x,seller=None):
        seller=seller or self._seller(x.seller_tenant_id)
        stock=self._stock(x)
        return {'id':x.id,'slug':x.slug,'title':x.title,'description':x.description,'listing_type':x.listing_type,'currency':x.currency,'unit_price':str(x.unit_price),'stock':str(stock) if stock is not None else None,'category_id':x.category_id,'product_id':x.product_id,'sku_id':x.sku_id,'offer_id':x.offer_id,'seller':{'tenant_id':seller.tenant_id,'slug':seller.slug,'display_name':seller.display_name,'seller_type':seller.seller_type},'moderation_status':x.moderation_status}

    def _offer_stock(self, offer):
        sku=self.db.get(MarketplaceSKU, offer.sku_id)
        if not sku or not sku.item_id or offer.stock_policy=='unmanaged': return Decimal('999999999')
        from app.engines.inventory.production import InventoryProductionService
        try:
            return max(Decimal('0'), Decimal(str(InventoryProductionService(self.db).snapshot(offer.seller_tenant_id, sku.item_id, offer.warehouse_id).available)))
        except Exception:
            return Decimal('0')

    def set_catalog_group(self, tenant_id:int, product_id:int, catalog_key:str):
        product=self.db.scalar(select(MarketplaceProduct).where(MarketplaceProduct.id==product_id, MarketplaceProduct.seller_tenant_id==tenant_id))
        if not product: raise MarketplaceError('product not found in seller tenant')
        key=catalog_key.strip().lower()
        if not key: raise MarketplaceError('catalog key is required')
        group=self.db.scalar(select(MarketplaceCatalogGroup).where(MarketplaceCatalogGroup.catalog_key==key))
        if not group:
            group=MarketplaceCatalogGroup(catalog_key=key,title=product.name,brand=product.brand,status='active'); self.db.add(group); self.db.flush()
        product.catalog_group_id=group.id; product.updated_at=datetime.now(timezone.utc); self.db.commit(); return group

    def offer_competition(self, catalog_group_id:int, currency:str|None=None, market_id:int|None=None):
        market_id=self._market_id(market_id)
        if currency is None:
            market=self.db.get(MarketContext, market_id)
            currency=market.default_currency if market else None
        currency=self._assert_currency(market_id,currency)
        group=self.db.scalar(select(MarketplaceCatalogGroup).where(MarketplaceCatalogGroup.id==catalog_group_id, MarketplaceCatalogGroup.status=='active'))
        if not group: raise MarketplaceError('catalog group not found')
        currency=(currency or '').strip().upper() or None
        rows=self.db.execute(select(MarketplaceOffer,MarketplaceListing,MarketplaceSellerProfile,MarketplaceSellerVerification)
            .join(MarketplaceSKU,MarketplaceSKU.id==MarketplaceOffer.sku_id)
            .join(MarketplaceProduct,MarketplaceProduct.id==MarketplaceSKU.product_id)
            .join(MarketplaceListing,MarketplaceListing.offer_id==MarketplaceOffer.id)
            .join(MarketplaceSellerProfile,MarketplaceSellerProfile.tenant_id==MarketplaceOffer.seller_tenant_id)
            .join(MarketplaceSellerVerification,MarketplaceSellerVerification.seller_tenant_id==MarketplaceOffer.seller_tenant_id)
            .where(MarketplaceProduct.catalog_group_id==catalog_group_id, MarketplaceOffer.market_id==market_id, MarketplaceListing.market_id==market_id, MarketplaceOffer.status=='active', MarketplaceListing.status=='published', MarketplaceListing.moderation_status=='approved', MarketplaceSellerProfile.status=='active', MarketplaceSellerVerification.status=='approved')).all()
        candidates=[]
        for offer,listing,seller,verification in rows:
            if currency and offer.currency!=currency: continue
            stock=self._offer_stock(offer)
            if stock<=0: continue
            # Deterministic weighted score: landed price (50%), delivery speed (25%), stock confidence (10%), seller rating (15%).
            landed=Decimal(str(offer.unit_price))+Decimal(str(offer.shipping_fee))
            delivery=Decimal(max(0,100-(offer.delivery_days or 7)*10))
            stock_score=min(100, stock)
            rating=Decimal('0')
            # Existing review aggregate is used only as a bounded seller-quality signal.
            avg=self.db.scalar(select(func.avg(MarketplaceReview.rating)).where(MarketplaceReview.listing_id==listing.id, MarketplaceReview.status=='published'))
            if avg is not None: rating=Decimal(str(avg))*20
            candidates.append((offer,listing,seller,landed,delivery,stock_score,rating,stock))
        if not candidates: raise MarketplaceError('no eligible offers for featured offer')
        min_landed=min(x[3] for x in candidates)
        max_landed=max(x[3] for x in candidates)
        def price_score(v):
            if max_landed==min_landed: return Decimal('100')
            return ((max_landed-v)/(max_landed-min_landed)*Decimal('100')).quantize(Decimal('0.00000001'))
        ranked=[]
        for item in candidates:
            offer,listing,seller,landed,delivery,stock_score,rating,stock=item
            score=(price_score(landed)*Decimal('.50')+delivery*Decimal('.25')+stock_score*Decimal('.10')+rating*Decimal('.15')).quantize(Decimal('0.00000001'))
            ranked.append((score,offer.id, item))
        ranked.sort(key=lambda x:(-x[0],x[1]))
        comp=self.db.scalar(select(MarketplaceOfferCompetition).where(MarketplaceOfferCompetition.market_id==market_id,MarketplaceOfferCompetition.catalog_group_id==catalog_group_id))
        if not comp: comp=MarketplaceOfferCompetition(market_id=market_id,catalog_group_id=catalog_group_id,currency=ranked[0][2][0].currency,reason='price50_delivery25_stock10_seller15'); self.db.add(comp); self.db.flush()
        else: comp.currency=ranked[0][2][0].currency; comp.calculated_at=datetime.now(timezone.utc); self.db.query(MarketplaceOfferCompetitionScore).filter(MarketplaceOfferCompetitionScore.competition_id==comp.id).delete(synchronize_session=False)
        comp.featured_offer_id=ranked[0][2][0].id
        for rank,(score,_,item) in enumerate(ranked,1):
            offer,listing,seller,landed,delivery,stock_score,rating,stock=item
            self.db.add(MarketplaceOfferCompetitionScore(competition_id=comp.id,offer_id=offer.id,seller_tenant_id=offer.seller_tenant_id,currency=offer.currency,unit_price=offer.unit_price,shipping_fee=offer.shipping_fee,stock=stock,delivery_days=offer.delivery_days,seller_rating_bps=int(rating*100),score=score,eligible=True,rank=rank))
        self.db.commit()
        return {'catalog_group':{'id':group.id,'catalog_key':group.catalog_key,'title':group.title,'brand':group.brand},'featured_offer_id':comp.featured_offer_id,'offers':[{'offer_id':item[2][0].id,'listing_id':item[2][1].id,'seller_tenant_id':item[2][0].seller_tenant_id,'unit_price':str(item[2][0].unit_price),'shipping_fee':str(item[2][0].shipping_fee),'currency':item[2][0].currency,'stock':str(item[2][7]),'delivery_days':item[2][0].delivery_days,'score':str(item[0]),'rank':rank,'featured':rank==1} for rank,item in enumerate(ranked,1)]}

    def ensure_buyer(self,user_id,display_name=None,phone=None):
        user=self.db.scalar(select(User).where(User.id==user_id,User.active.is_(True)))
        if not user: raise MarketplaceError('active user required')
        x=self.db.scalar(select(MarketplaceBuyerProfile).where(MarketplaceBuyerProfile.user_id==user_id))
        if not x:
            x=MarketplaceBuyerProfile(user_id=user_id,display_name=(display_name or user.email).strip(),phone=phone); self.db.add(x); self.db.commit()
        return x

    def add_address(self,user_id, label, recipient_name, phone, governorate, city, address_line, landmark=None,
                    country_code=None, market_id=None, governorate_id=None, district_id=None, locality_id=None,
                    neighborhood=None, street=None, building=None, geo_lat=None, geo_lng=None,
                    address_confidence='low', delivery_instructions=None):
        self.ensure_buyer(user_id)
        if not all([label,recipient_name,phone,governorate,city,address_line]): raise MarketplaceError('complete address is required')
        if address_confidence not in {'high','medium','low'}: raise MarketplaceError('invalid address confidence')
        if geo_lat is not None and not (-90 <= float(geo_lat) <= 90): raise MarketplaceError('invalid latitude')
        if geo_lng is not None and not (-180 <= float(geo_lng) <= 180): raise MarketplaceError('invalid longitude')
        if market_id is not None:
            market_id=self._market_id(market_id)
            governorate_id,district_id,locality_id,_=self._resolve_geography(market_id,governorate_id=governorate_id,district_id=district_id,locality_id=locality_id,governorate=governorate,city=city)
            if os.getenv('ENVIRONMENT','dev')=='production' and governorate_id is None:
                raise MarketplaceError('structured governorate_id is required for production addresses')
        x=MarketplaceAddress(
            user_id=user_id,label=label,recipient_name=recipient_name,phone=phone,governorate=governorate,city=city,
            address_line=address_line,landmark=landmark,country_code=country_code,market_id=market_id,
            governorate_id=governorate_id,district_id=district_id,locality_id=locality_id,neighborhood=neighborhood,
            street=street,building=building,geo_lat=geo_lat,geo_lng=geo_lng,address_confidence=address_confidence,
            delivery_instructions=delivery_instructions,active=True)
        self.db.add(x); self.db.commit(); return x

    def cart(self,user_id,market_id=None):
        self.ensure_buyer(user_id); market_id=self._market_id(market_id)
        x=self.db.scalar(select(MarketplaceCart).where(MarketplaceCart.buyer_user_id==user_id,MarketplaceCart.market_id==market_id,MarketplaceCart.status=='active'))
        if not x:
            x=MarketplaceCart(buyer_user_id=user_id,market_id=market_id,status='active'); self.db.add(x); self.db.commit(); self.db.refresh(x)
        return x

    def add_to_cart(self,user_id,listing_id,quantity):
        q=_positive(quantity,'quantity'); listing=self._listing(listing_id,public=True); cart=self.cart(user_id,listing.market_id)
        if listing.market_id is None: raise MarketplaceError('listing market is required')
        item=self.db.scalar(select(MarketplaceCartItem).where(MarketplaceCartItem.cart_id==cart.id,MarketplaceCartItem.listing_id==listing_id))
        if item: item.quantity=_money(item.quantity)+q
        else: self.db.add(MarketplaceCartItem(cart_id=cart.id,listing_id=listing_id,quantity=q))
        cart.updated_at=datetime.now(timezone.utc); self.db.commit(); return cart

    def remove_from_cart(self,user_id,listing_id):
        listing=self._listing(listing_id,public=True); cart=self.cart(user_id,listing.market_id); item=self.db.scalar(select(MarketplaceCartItem).where(MarketplaceCartItem.cart_id==cart.id,MarketplaceCartItem.listing_id==listing_id))
        if item: self.db.delete(item); cart.updated_at=datetime.now(timezone.utc); self.db.commit()
        return cart

    def cart_view(self,user_id,market_id=None):
        cart=self.cart(user_id,market_id); rows=self.db.execute(select(MarketplaceCartItem,MarketplaceListing,MarketplaceSellerProfile).join(MarketplaceListing,MarketplaceListing.id==MarketplaceCartItem.listing_id).join(MarketplaceSellerProfile,MarketplaceSellerProfile.tenant_id==MarketplaceListing.seller_tenant_id).where(MarketplaceCartItem.cart_id==cart.id)).all()
        items=[]
        for ci,l,s in rows:
            items.append({'id':ci.id,'listing':self._listing_view(l,s),'quantity':str(ci.quantity),'line_total':str(_money(ci.quantity)*_money(l.unit_price))})
        market=self.db.get(MarketContext,cart.market_id) if cart.market_id is not None else None
        return {'id':cart.id,'status':cart.status,'market_id':cart.market_id,'market_code':market.code if market else None,'items':items}

    def checkout(self,user_id, shipping_address_id=None, shipping_fee=Decimal('0'), platform_fee_bps=None, shipping_quote_id=None, shipping_quote_ids=None, market_id=None, payment_method_code=None, idempotency_key=None, idempotency_tenant_id=None, idempotency_request_hash=None):
        idempotency_record = None
        if idempotency_key is not None:
            key = str(idempotency_key).strip()
            if not key or len(key) > 255:
                raise MarketplaceError('idempotency key must be between 1 and 255 characters')
            if not idempotency_tenant_id:
                raise MarketplaceError('idempotency tenant context is required')
            if not idempotency_request_hash or len(str(idempotency_request_hash)) != 64:
                raise MarketplaceError('idempotency request hash is required')
            try:
                int(str(idempotency_request_hash), 16)
            except ValueError:
                raise MarketplaceError('idempotency request hash is invalid')
            try:
                with self.db.begin_nested():
                    idempotency_record = IdempotencyRecord(
                        tenant_id=idempotency_tenant_id,
                        key=key,
                        request_hash=str(idempotency_request_hash).lower(),
                        response_json='__pending__',
                    )
                    self.db.add(idempotency_record)
                    self.db.flush()
            except IntegrityError:
                existing = self.db.scalar(select(IdempotencyRecord).where(
                    IdempotencyRecord.tenant_id == idempotency_tenant_id,
                    IdempotencyRecord.key == key,
                ))
                if existing is None:
                    raise MarketplaceError('idempotent request could not be resolved; retry safely')
                if existing.request_hash != str(idempotency_request_hash).lower():
                    raise MarketplaceError('idempotency key was already used for a different request')
                if existing.response_json == '__pending__':
                    raise MarketplaceError('idempotent request is still in progress')
                try:
                    stored = json.loads(existing.response_json)
                    order_ids = [int(x) for x in stored.get('order_ids', [])]
                except (TypeError, ValueError, AttributeError):
                    raise MarketplaceError('stored idempotency result is invalid')
                if not order_ids:
                    raise MarketplaceError('stored idempotency result is empty')
                return self.db.scalars(select(MarketplaceOrder).where(
                    MarketplaceOrder.id.in_(order_ids)
                ).order_by(MarketplaceOrder.id)).all()

        if platform_fee_bps is not None:
            raise MarketplaceError('platform fee is policy-controlled; client-supplied platform_fee_bps is not accepted')
        self.ensure_buyer(user_id)
        active_carts=self.db.scalars(select(MarketplaceCart).where(MarketplaceCart.buyer_user_id==user_id,MarketplaceCart.status=='active').order_by(MarketplaceCart.id)).all()
        if not active_carts: raise MarketplaceError('cart is empty')
        if market_id is None:
            if len(active_carts) != 1: raise MarketplaceError('market context is required when buyer has multiple active carts')
            cart=active_carts[0]
            market_id=cart.market_id
        else:
            cart=next((x for x in active_carts if x.market_id==market_id),None)
            if cart is None: raise MarketplaceError('cart not found for market')
        if market_id is None: raise MarketplaceError('cart market is required')
        if payment_method_code is not None:
            payment_method_code = str(payment_method_code).strip().lower()
            method = self.db.scalar(select(PaymentMethodCatalogEntry).where(
                PaymentMethodCatalogEntry.market_id == market_id,
                PaymentMethodCatalogEntry.code == payment_method_code,
                PaymentMethodCatalogEntry.active.is_(True),
            ))
            if method is None: raise MarketplaceError('payment method is not available in this market')
        if cart.status!='active': raise MarketplaceError('cart is not active')
        rows=self.db.execute(select(MarketplaceCartItem,MarketplaceListing,MarketplaceSellerProfile).join(MarketplaceListing,MarketplaceListing.id==MarketplaceCartItem.listing_id).join(MarketplaceSellerProfile,MarketplaceSellerProfile.tenant_id==MarketplaceListing.seller_tenant_id).join(MarketplaceSellerVerification,MarketplaceSellerVerification.seller_tenant_id==MarketplaceListing.seller_tenant_id).where(MarketplaceCartItem.cart_id==cart.id,MarketplaceListing.market_id==market_id,MarketplaceListing.status=='published',MarketplaceListing.moderation_status=='approved',MarketplaceSellerProfile.status=='active',MarketplaceSellerVerification.status=='approved')).all()
        if not rows: raise MarketplaceError('cart is empty')
        if shipping_address_id:
            address=self.db.scalar(select(MarketplaceAddress).where(MarketplaceAddress.id==shipping_address_id,MarketplaceAddress.user_id==user_id,MarketplaceAddress.active.is_(True)))
            if not address: raise MarketplaceError('shipping address does not belong to buyer')
            if address.market_id is None and os.getenv('ENVIRONMENT','dev')!='production':
                address.market_id=market_id; self.db.flush()
            if address.market_id != market_id: raise MarketplaceError('shipping address does not belong to buyer')
        quote_ids=list(shipping_quote_ids or [])
        if shipping_quote_id is not None:
            quote_ids.append(shipping_quote_id)
        if len(set(quote_ids)) != len(quote_ids):
            raise MarketplaceError('shipping quote references must be unique')
        quotes=[]
        quote_by_seller={}
        if quote_ids:
            now=datetime.now(timezone.utc)
            for qid in quote_ids:
                q=self.db.scalar(select(MarketplaceShippingQuote).where(MarketplaceShippingQuote.id==qid,MarketplaceShippingQuote.market_id==market_id,MarketplaceShippingQuote.buyer_user_id==user_id).with_for_update())
                expires=q.expires_at.replace(tzinfo=timezone.utc) if q and q.expires_at.tzinfo is None else (q.expires_at if q else now)
                if not q or q.consumed_at or expires < now: raise MarketplaceError('shipping quote is invalid or expired')
                if shipping_address_id != q.address_id: raise MarketplaceError('shipping quote does not match address')
                quotes.append(q)
            if any(q.currency.upper() != str(rows[0][1].currency).upper() for q in quotes):
                raise MarketplaceError('shipping quote currency does not match cart currency')
            quote_by_seller={q.seller_tenant_id: _money(q.fee) for q in quotes}
            if len(quote_by_seller) != len(quotes): raise MarketplaceError('only one shipping quote is allowed per seller')
            shipping_fee=sum(quote_by_seller.values(),Decimal('0'))
        elif _money(shipping_fee) != Decimal('0'):
            raise MarketplaceError('shipping fee must come from a server-issued shipping quote')
        groups={}
        for ci,l,s in rows:
            groups.setdefault((s.tenant_id,l.currency),[]).append((ci,l,s))
        if quotes:
            quote_sellers={q.seller_tenant_id for q in quotes}
            cart_sellers={seller_id for seller_id,_ in groups}
            if quote_sellers != cart_sellers:
                raise MarketplaceError('one shipping quote is required for every seller in the cart')
        # One customer-facing order groups all seller orders. Currency mixing is not silently converted.
        currencies={currency for _,currency in groups}
        if len(currencies) != 1: raise MarketplaceError('cart contains multiple currencies; checkout requires one currency')
        customer_currency=next(iter(currencies))
        customer_subtotal=sum((_money(ci.quantity)*_money(l.unit_price) for group in groups.values() for ci,l,_ in group),Decimal('0'))
        customer_shipping=_money(shipping_fee)
        customer_order=MarketplaceCustomerOrder(market_id=market_id,reference=f'HUS-{uuid4().hex[:20].upper()}',buyer_user_id=user_id,currency=customer_currency,subtotal=customer_subtotal,shipping_fee=customer_shipping,total=customer_subtotal+customer_shipping,shipping_address_id=shipping_address_id,status='pending_payment',payment_method_code=payment_method_code)
        self.db.add(customer_order); self.db.flush()
        created=[]
        for (seller_id,currency), group in groups.items():
            subtotal=sum((_money(ci.quantity)*_money(l.unit_price) for ci,l,_ in group),Decimal('0'))
            category_ids={l.category_id for ci,l,_ in group if l.category_id is not None}
            fee_rule, fee=self.marketplace_fee_preview(seller_id, subtotal, currency, category_ids, market_id)
            seller_shipping_fee=quote_by_seller.get(seller_id, Decimal('0')) if quotes else _money(shipping_fee)
            total=subtotal+seller_shipping_fee
            ref=f'MKT-{uuid4().hex[:20].upper()}'
            product_lines=[]
            for ci,l,_ in group:
                if l.listing_type=='product':
                    if l.stock_policy=='managed' and (_money(ci.quantity) > (self._stock(l) or Decimal('0'))): raise MarketplaceError(f'insufficient stock for listing {l.id}')
                    product_lines.append(OrderLineInput(item_id=l.item_id,quantity=_money(ci.quantity),unit_price=_money(l.unit_price)))
            sales=None
            if product_lines:
                # Commerce is authoritative for reservation; this stage is deliberately explicit and recoverable.
                wh=group[0][1].warehouse_id
                commerce=CommerceProductionService(self.db)
                sales=commerce.create_draft(tenant_id=seller_id,reference=f'MKT-SALE:{ref}',warehouse_id=wh,currency=currency,lines=product_lines,commit=False)
                commerce.confirm(seller_id,sales.id,commit=False)
            order=MarketplaceOrder(market_id=market_id,reference=ref,buyer_user_id=user_id,customer_order_id=customer_order.id,seller_tenant_id=seller_id,sales_order_id=sales.id if sales else None,shipping_address_id=shipping_address_id,currency=currency,subtotal=subtotal,shipping_fee=seller_shipping_fee,platform_fee=fee,total=total,status='pending_payment',payment_method_code=payment_method_code)
            self.db.add(order); self.db.flush()
            seller_order=MarketplaceSellerOrder(customer_order_id=customer_order.id,marketplace_order_id=order.id,seller_tenant_id=seller_id,status='pending_payment',subtotal=subtotal,shipping_fee=seller_shipping_fee,total=total)
            self.db.add(seller_order); self.db.flush()
            self.db.add(MarketplaceFulfillment(seller_order_id=seller_order.id,seller_tenant_id=seller_id,method='seller_fulfilled',status='pending'))
            sales_lines=self.db.scalars(select(SalesOrderLine).where(SalesOrderLine.order_id==sales.id).order_by(SalesOrderLine.id)) .all() if sales else []
            j=0
            for ci,l,_ in group:
                line_total=_money(ci.quantity)*_money(l.unit_price)
                self.db.add(MarketplaceOrderLine(marketplace_order_id=order.id,listing_id=l.id,sales_order_line_id=sales_lines[j].id if j<len(sales_lines) else None,title_snapshot=l.title,quantity=_money(ci.quantity),unit_price=_money(l.unit_price),line_total=line_total)); j+=1
            self.db.add(MarketplaceOrderFee(marketplace_order_id=order.id,seller_tenant_id=seller_id,rule_id=fee_rule.id if fee_rule.id else None,fee_type='commission',basis_amount=subtotal,commission_bps=fee_rule.commission_bps,fixed_fee=_money(fee_rule.fixed_fee),amount=fee,currency=currency,policy_version=fee_rule.policy_version,policy_snapshot={'name':fee_rule.name,'scope':fee_rule.scope,'market_id':fee_rule.market_id,'seller_tenant_id':fee_rule.seller_tenant_id,'category_id':fee_rule.category_id,'commission_bps':fee_rule.commission_bps,'fixed_fee':str(_money(fee_rule.fixed_fee)),'currency':fee_rule.currency,'priority':fee_rule.priority}))
            self.db.add(MarketplacePayout(market_id=market_id,seller_tenant_id=seller_id,marketplace_order_id=order.id,reference=f'PAYOUT:{ref}',gross_amount=total,seller_funded_discount=Decimal('0'),platform_funded_discount=Decimal('0'),platform_fee=fee,net_amount=total-fee,currency=currency,status='held'))
            line_rows=self.db.scalars(select(MarketplaceOrderLine).where(MarketplaceOrderLine.marketplace_order_id==order.id).order_by(MarketplaceOrderLine.id)).all()
            remaining_fee=fee; remaining_shipping=seller_shipping_fee
            for idx,line in enumerate(line_rows):
                is_last=idx==len(line_rows)-1
                share=line_total=line.line_total
                if is_last:
                    line_fee=remaining_fee; line_shipping=remaining_shipping
                else:
                    ratio=(Decimal(str(line.line_total))/subtotal) if subtotal else Decimal('0')
                    line_fee=_money(fee*ratio); line_shipping=_money(seller_shipping_fee*ratio)
                    remaining_fee-=line_fee; remaining_shipping-=line_shipping
                line_net=_money(line.line_total+line_shipping-line_fee)
                self.db.add(MarketplaceOrderFinancialAllocation(marketplace_order_id=order.id,order_line_id=line.id,seller_order_id=seller_order.id,seller_tenant_id=seller_id,market_id=market_id,currency=currency,gross_amount=_money(line.line_total),shipping_amount=_money(line_shipping),discount_amount=Decimal('0'),platform_fee=_money(line_fee),net_amount=line_net,allocation_reference=f'ALLOC:{ref}:{line.id}'))
            self._event(seller_id,'marketplace.order.created','marketplace_order',order.id,{'reference':ref,'buyer_user_id':user_id,'total':str(total),'currency':currency})
            self.db.flush(); created.append(order)
            for quote in quotes:
                quote.consumed_at=datetime.now(timezone.utc)
        # The selected market cart is materialized into immutable orders; other market carts remain untouched.
        for ci in list(self.db.scalars(select(MarketplaceCartItem).where(MarketplaceCartItem.cart_id==cart.id)).all()):
            self.db.delete(ci)
        cart.status='active'; cart.updated_at=datetime.now(timezone.utc)
        # Runtime financial conservation gate: checkout cannot commit an order whose
        # line allocations/payout snapshot do not reconcile.
        for created_order in created:
            self.assert_financial_invariants(created_order.id)
        if idempotency_record is not None:
            idempotency_record.response_json = json.dumps(
                {'order_ids': [o.id for o in created]},
                sort_keys=True,
                separators=(',', ':'),
            )
        self.db.commit()
        return created

    def assert_seller_balance_conservation(self, payout):
        """Validate seller-balance entries against the payout lifecycle.

        This is deliberately stricter than a running-balance calculation: it checks
        that lifecycle transitions have exactly the expected financial entries and
        that a paid payout cannot silently create or consume seller funds.
        """
        entries = self.db.scalars(select(MarketplaceSellerBalanceEntry).where(
            MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
            MarketplaceSellerBalanceEntry.seller_tenant_id == payout.seller_tenant_id,
            MarketplaceSellerBalanceEntry.market_id == payout.market_id,
            MarketplaceSellerBalanceEntry.currency == payout.currency,
        ).order_by(MarketplaceSellerBalanceEntry.id)).all()
        credits = [e for e in entries if e.entry_type == 'credit']
        payout_debits = [e for e in entries if e.entry_type == 'payout_debit']
        refund_reversals = [e for e in entries if e.entry_type == 'refund_reversal']
        refund_recoveries = [e for e in entries if e.entry_type == 'refund_recovery']
        other = [e for e in entries if e.entry_type not in {'credit', 'payout_debit', 'refund_reversal', 'refund_recovery'}]
        if other:
            raise MarketplaceError('unsupported seller balance entry type')
        if len(credits) > 1:
            raise MarketplaceError('seller payout has duplicate credit entries')
        credit_total = sum((_money(e.amount) for e in credits), Decimal('0'))
        reversal_total = sum((_money(e.amount) for e in refund_reversals), Decimal('0'))
        recovery_total = sum((_money(e.amount) for e in refund_recoveries), Decimal('0'))
        payout_debit_total = sum((_money(e.amount) for e in payout_debits), Decimal('0'))
        net = _money(payout.net_amount)

        if payout.status == 'paid':
            if len(payout_debits) != 1 or payout_debit_total != net:
                raise MarketplaceError('paid payout seller balance debit is not conserved')
            if refund_reversals:
                raise MarketplaceError('paid payout cannot contain refund reversal entries')
            if recovery_total > payout_debit_total:
                raise MarketplaceError('refund recovery exceeds paid seller proceeds')
            if credit_total != net:
                raise MarketplaceError('paid payout seller credit is not conserved')
        elif payout.status == 'reversed':
            if payout_debits or refund_recoveries:
                raise MarketplaceError('reversed payout cannot contain payout or recovery debits')
            if credit_total != net + reversal_total:
                raise MarketplaceError('reversed payout seller balance is not conserved')
        else:
            if payout_debits or refund_recoveries:
                raise MarketplaceError('unpaid payout cannot contain payout or recovery debits')
            if credit_total != net + reversal_total:
                raise MarketplaceError('unpaid payout seller balance is not conserved')
        return True

    def assert_financial_invariants(self, marketplace_order_id: int):
        """Validate order, line allocation, payout, and customer-order financial conservation.

        This is an assertion boundary, not a source of accounting truth: it never mutates
        financial state and raises when money would be created, lost, or allocated twice.
        """
        order = self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id == marketplace_order_id))
        if not order:
            raise MarketplaceError("marketplace order not found")
        qlines = self.db.scalars(select(MarketplaceOrderLine).where(MarketplaceOrderLine.marketplace_order_id == order.id).order_by(MarketplaceOrderLine.id)).all()
        allocations = self.db.scalars(select(MarketplaceOrderFinancialAllocation).where(MarketplaceOrderFinancialAllocation.marketplace_order_id == order.id)).all()
        payout = self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == order.id))

        money = lambda v: _money(v)
        line_gross = sum((money(x.line_total) for x in qlines), Decimal("0"))
        alloc_gross = sum((money(x.gross_amount) for x in allocations), Decimal("0"))
        alloc_shipping = sum((money(x.shipping_amount) for x in allocations), Decimal("0"))
        alloc_discount = sum((money(x.discount_amount) for x in allocations), Decimal("0"))
        alloc_fee = sum((money(x.platform_fee) for x in allocations), Decimal("0"))
        alloc_net = sum((money(x.net_amount) for x in allocations), Decimal("0"))
        discount_rows = self.db.scalars(
            select(MarketplaceDiscountAllocation).where(
                MarketplaceDiscountAllocation.customer_order_id == order.customer_order_id,
                MarketplaceDiscountAllocation.seller_order_id.in_(
                    select(MarketplaceSellerOrder.id).where(MarketplaceSellerOrder.marketplace_order_id == order.id)
                ),
            )
        ).all() if order.customer_order_id else []
        authoritative_discount = sum((money(x.amount) for x in discount_rows), Decimal("0"))
        seller_funded_discount = sum((money(x.seller_funded_amount) for x in discount_rows if x.seller_funded_amount is not None), Decimal("0"))
        platform_funded_discount = sum((money(x.platform_funded_amount) for x in discount_rows if x.platform_funded_amount is not None), Decimal("0"))
        seller_order_ids = {x.id for x in self.db.scalars(
            select(MarketplaceSellerOrder).where(
                MarketplaceSellerOrder.marketplace_order_id == order.id
            )
        ).all()}
        checks = {
            "order_total": money(order.total) == money(order.subtotal) + money(order.shipping_fee) - authoritative_discount,
            "line_gross_matches_subtotal": line_gross == money(order.subtotal),
            "allocation_gross_matches_lines": alloc_gross == line_gross,
            "allocation_shipping_matches_order": alloc_shipping == money(order.shipping_fee),
            "allocation_fee_matches_order": alloc_fee == money(order.platform_fee),
            "allocation_discount_matches_authority": alloc_discount == seller_funded_discount,
            "discount_funding_conservation": all(x.seller_funded_amount is not None and x.platform_funded_amount is not None and money(x.seller_funded_amount) + money(x.platform_funded_amount) == money(x.amount) for x in discount_rows),
            "discount_funding_source_matches_amounts": all((x.funding_source == "seller" and money(x.seller_funded_amount) == money(x.amount) and money(x.platform_funded_amount) == 0) or (x.funding_source == "platform" and money(x.seller_funded_amount) == 0 and money(x.platform_funded_amount) == money(x.amount)) or (x.funding_source == "shared" and money(x.seller_funded_amount) + money(x.platform_funded_amount) == money(x.amount)) for x in discount_rows if x.seller_funded_amount is not None and x.platform_funded_amount is not None),
            "discount_total_matches_funding": seller_funded_discount + platform_funded_discount == authoritative_discount,
            "allocation_math": alloc_net == money(order.subtotal) + money(order.shipping_fee) - alloc_discount - alloc_fee,
            "allocation_count_matches_lines": len(allocations) == len(qlines),
            "allocation_currency_matches_order": all(x.currency == order.currency for x in allocations),
            "allocation_seller_matches_order": all(x.seller_tenant_id == order.seller_tenant_id for x in allocations),
            "allocation_market_matches_order": all(x.market_id == order.market_id for x in allocations),
            "discount_seller_order_matches_scope": all(x.seller_order_id in seller_order_ids for x in discount_rows),
            "discount_seller_matches_scope": all(
                x.seller_tenant_id == order.seller_tenant_id for x in discount_rows
            ),
            "discount_currency_matches_order": all(
                x.currency == order.currency for x in discount_rows
            ),
        }
        if payout:
            checks.update({
                "payout_gross_matches_order": money(payout.gross_amount) == money(order.subtotal) + money(order.shipping_fee),
                "payout_discount_snapshot_matches_authority": money(payout.seller_funded_discount) == seller_funded_discount and money(payout.platform_funded_discount) == platform_funded_discount,
                "payout_fee_matches_order": money(payout.platform_fee) == money(order.platform_fee),
                "payout_net_math": money(payout.net_amount) == money(payout.gross_amount) - money(payout.seller_funded_discount) - money(payout.platform_fee),
                "payout_currency_matches_order": payout.currency == order.currency,
            })
        else:
            checks["payout_exists"] = False

        if order.customer_order_id:
            children = self.db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id == order.customer_order_id)).all()
            customer = self.db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.id == order.customer_order_id))
            if customer:
                checks.update({
                    "customer_subtotal_conservation": sum((money(x.subtotal) for x in children), Decimal("0")) == money(customer.subtotal),
                    "customer_shipping_conservation": sum((money(x.shipping_fee) for x in children), Decimal("0")) == money(customer.shipping_fee),
                    "customer_total_conservation": sum((money(x.total) for x in children), Decimal("0")) == money(customer.total),
                    "customer_currency_matches": all(x.currency == customer.currency for x in [order]),
                })

        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise MarketplaceError("financial invariant violation: " + ", ".join(failed))
        return {"marketplace_order_id": order.id, "currency": order.currency, "checks": checks, "allocation_net": str(alloc_net)}

    def financial_reconciliation_report(self, marketplace_order_id: int):
        """Return a read-only end-to-end money trail for one marketplace order.

        This report joins order allocation, customer payment, provider settlement,
        reconciliation, seller payout, and seller-balance effects. It never mutates
        financial state; any invariant failure is surfaced as an exception.
        """
        order = self.db.get(MarketplaceOrder, marketplace_order_id)
        if not order:
            raise MarketplaceError("marketplace order not found")
        customer = self.db.get(MarketplaceCustomerOrder, order.customer_order_id) if order.customer_order_id else None
        session = self.db.scalar(select(MarketplacePaymentSession).where(
            MarketplacePaymentSession.customer_order_id == order.customer_order_id
        )) if order.customer_order_id else None
        allocations = self.db.scalars(select(MarketplacePaymentAllocation).where(
            MarketplacePaymentAllocation.marketplace_order_id == order.id
        ).order_by(MarketplacePaymentAllocation.id)).all()
        intents = []
        settlements = []
        reconciliations = []
        for allocation in allocations:
            intent = self.db.scalar(select(PaymentIntent).where(
                PaymentIntent.tenant_id == allocation.seller_tenant_id,
                PaymentIntent.reference == allocation.payment_reference
            ))
            if intent:
                intents.append(intent)
            settlements.extend(self.db.scalars(select(PaymentSettlement).where(
                PaymentSettlement.tenant_id == allocation.seller_tenant_id,
                PaymentSettlement.payment_reference == allocation.payment_reference
            )).all())
            reconciliations.extend(self.db.scalars(select(PaymentReconciliation).where(
                PaymentReconciliation.tenant_id == allocation.seller_tenant_id,
                PaymentReconciliation.internal_reference == allocation.payment_reference
            )).all())
        payout = self.db.scalar(select(MarketplacePayout).where(
            MarketplacePayout.marketplace_order_id == order.id
        ))
        balance_entries = self.db.scalars(select(MarketplaceSellerBalanceEntry).where(
            MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id
        ).order_by(MarketplaceSellerBalanceEntry.id)).all() if payout else []

        self.assert_financial_invariants(order.id)
        if session:
            self.assert_payment_conservation(session.id)
        if payout and (balance_entries or payout.status in {'paid', 'reversed'}):
            self.assert_seller_balance_conservation(payout)

        payment_amount = sum((_money(x.amount) for x in intents if x.status in {'captured','authorized','refunded'}), Decimal('0'))
        settlement_amount = sum((_money(x.amount) for x in settlements if x.status == 'settled'), Decimal('0'))
        reconciled_amount = sum((_money(x.actual_amount) for x in reconciliations if x.status == 'matched'), Decimal('0'))
        credit_amount = sum((_money(x.amount) for x in balance_entries if x.entry_type == 'credit'), Decimal('0'))
        payout_debit_amount = sum((_money(x.amount) for x in balance_entries if x.entry_type == 'payout_debit'), Decimal('0'))
        recovery_amount = sum((_money(x.amount) for x in balance_entries if x.entry_type == 'refund_recovery'), Decimal('0'))
        reversal_amount = sum((_money(x.amount) for x in balance_entries if x.entry_type == 'refund_reversal'), Decimal('0'))

        exceptions = []
        if customer and _money(session.amount) != _money(customer.total) if session else False:
            exceptions.append('customer_payment_session_amount')
        if session and payment_amount and payment_amount != _money(session.amount):
            exceptions.append('payment_intent_amount')
        if settlement_amount and payment_amount and settlement_amount != payment_amount:
            exceptions.append('settlement_amount')
        if reconciliations and reconciled_amount and settlement_amount and reconciled_amount != settlement_amount:
            exceptions.append('reconciliation_amount')
        if payout and payout.status == 'paid' and payout_debit_amount != _money(payout.net_amount):
            exceptions.append('payout_debit_amount')
        if payout and credit_amount and payout_debit_amount > credit_amount + reversal_amount + recovery_amount:
            exceptions.append('seller_balance_consumption')
        return {
            'marketplace_order_id': order.id,
            'customer_order_id': order.customer_order_id,
            'market_id': order.market_id,
            'currency': order.currency,
            'order': {'subtotal': str(_money(order.subtotal)), 'shipping': str(_money(order.shipping_fee)), 'platform_fee': str(_money(order.platform_fee)), 'total': str(_money(order.total)), 'status': order.status},
            'payment': {'session_reference': session.reference if session else None, 'status': session.status if session else None, 'amount': str(_money(session.amount)) if session else None, 'intent_count': len(intents), 'captured_amount': str(payment_amount)},
            'settlement': {'count': len(settlements), 'settled_amount': str(settlement_amount), 'reconciled_amount': str(reconciled_amount), 'statuses': sorted({x.reconciliation_status for x in settlements})},
            'seller': {'payout_status': payout.status if payout else None, 'payout_net': str(_money(payout.net_amount)) if payout else None, 'credit': str(credit_amount), 'payout_debit': str(payout_debit_amount), 'refund_recovery': str(recovery_amount), 'refund_reversal': str(reversal_amount)},
            'exceptions': exceptions,
            'status': 'balanced' if not exceptions else 'exception',
        }

    def assert_refund_invariants(self, marketplace_order_id: int, payment_refund_id: int):
        """Validate refund conservation without rewriting immutable order allocation history.

        Refunds are lifecycle adjustments; the original order allocation remains the
        historical basis, while payout/balance effects are validated separately.
        """
        order = self.db.get(MarketplaceOrder, marketplace_order_id)
        refund = self.db.get(PaymentRefund, payment_refund_id)
        if not order or not refund:
            raise MarketplaceError('refund invariant target not found')
        if refund.currency != order.currency or _money(refund.amount) <= 0 or _money(refund.amount) > _money(order.total):
            raise MarketplaceError('refund invariant violation: refund amount/currency')
        if refund.status != 'succeeded':
            raise MarketplaceError('refund invariant violation: refund not completed')
        payout = self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == order.id))
        if payout:
            if payout.currency != order.currency or _money(payout.net_amount) != max(Decimal('0'), _money(payout.gross_amount) - _money(payout.seller_funded_discount) - _money(payout.platform_fee)):
                raise MarketplaceError('refund invariant violation: payout math')
            if payout.status == 'reversed' and _money(payout.net_amount) != 0:
                raise MarketplaceError('refund invariant violation: reversed payout retains balance')
            recoveries = self.db.scalars(select(MarketplaceSellerBalanceEntry).where(
                MarketplaceSellerBalanceEntry.marketplace_payout_id == payout.id,
                MarketplaceSellerBalanceEntry.entry_type == 'refund_recovery')).all()
            recovery_total = sum((_money(x.amount) for x in recoveries), Decimal('0'))
            if recovery_total < 0:
                raise MarketplaceError('refund invariant violation: negative recovery')
            if payout.status == 'paid' and recovery_total > _money(payout.net_amount):
                raise MarketplaceError('refund invariant violation: recovery exceeds seller proceeds')
        return {'marketplace_order_id': order.id, 'refund_id': refund.id, 'amount': str(_money(refund.amount)), 'currency': refund.currency}

    def financial_allocation(self, marketplace_order_id:int):
        """Return immutable line-level financial allocation for one seller order."""
        rows=self.db.scalars(select(MarketplaceOrderFinancialAllocation).where(MarketplaceOrderFinancialAllocation.marketplace_order_id==marketplace_order_id).order_by(MarketplaceOrderFinancialAllocation.order_line_id)).all()
        return [{"order_line_id":x.order_line_id,"seller_order_id":x.seller_order_id,"seller_tenant_id":x.seller_tenant_id,"market_id":x.market_id,"currency":x.currency,"gross":str(x.gross_amount),"shipping":str(x.shipping_amount),"discount":str(x.discount_amount),"platform_fee":str(x.platform_fee),"net":str(x.net_amount),"reference":x.allocation_reference} for x in rows]

    def customer_order_view(self, buyer_user_id:str, customer_order_id:int):
        co=self.db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.id==customer_order_id,MarketplaceCustomerOrder.buyer_user_id==buyer_user_id))
        if not co: raise MarketplaceError('customer order not found')
        rows=self.db.execute(select(MarketplaceSellerOrder,MarketplaceOrder,MarketplaceFulfillment).join(MarketplaceOrder,MarketplaceOrder.id==MarketplaceSellerOrder.marketplace_order_id).outerjoin(MarketplaceFulfillment,MarketplaceFulfillment.seller_order_id==MarketplaceSellerOrder.id).where(MarketplaceSellerOrder.customer_order_id==co.id).order_by(MarketplaceSellerOrder.id)).all()
        sellers=[]
        for so,mo,fulfillment in rows:
            shipment=None
            if fulfillment and fulfillment.shipment_id:
                from app.core.models.logistics import Shipment
                sh=self.db.scalar(select(Shipment).where(Shipment.id==fulfillment.shipment_id,Shipment.tenant_id==so.seller_tenant_id))
                if sh:
                    shipment={'id':sh.id,'reference':sh.reference,'carrier':sh.carrier,'tracking_number':sh.tracking_number,'status':sh.status,'destination':sh.destination}
            sellers.append({'id':so.id,'seller_tenant_id':so.seller_tenant_id,'marketplace_order_id':mo.id,'reference':mo.reference,'status':so.status,'subtotal':str(so.subtotal),'shipping_fee':str(so.shipping_fee),'total':str(so.total),'fulfillment':None if not fulfillment else {'id':fulfillment.id,'method':fulfillment.method,'status':fulfillment.status,'shipment_id':fulfillment.shipment_id,'carrier':fulfillment.carrier,'assigned_at':fulfillment.assigned_at.isoformat() if fulfillment.assigned_at else None,'shipment':shipment}})
        return {'id':co.id,'reference':co.reference,'status':co.status,'currency':co.currency,'subtotal':str(co.subtotal),'shipping_fee':str(co.shipping_fee),'total':str(co.total),'shipping_address_id':co.shipping_address_id,'seller_orders':sellers,'created_at':co.created_at.isoformat()}

    def customer_orders(self,buyer_user_id:str):
        rows=self.db.scalars(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.buyer_user_id==buyer_user_id).order_by(MarketplaceCustomerOrder.id.desc())).all()
        return [self.customer_order_view(buyer_user_id,x.id) for x in rows]

    def _sync_customer_order(self, customer_order_id:int|None):
        if not customer_order_id: return
        co=self.db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.id==customer_order_id).with_for_update())
        if not co: return
        children=self.db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id==co.id)).all()
        if not children: return
        statuses={x.status for x in children}
        if statuses == {'paid'}: co.status='paid'
        elif statuses <= {'processing','ready_for_fulfillment'} and 'paid' not in statuses: co.status='processing'
        elif statuses <= {'fulfilled'}: co.status='completed'
        elif 'disputed' in statuses: co.status='disputed'
        elif 'refunded' in statuses: co.status='refunded'
        elif statuses <= {'cancelled'}: co.status='cancelled'
        elif any(x in statuses for x in {'processing','ready_for_fulfillment','fulfilled'}): co.status='processing'
        co.updated_at=datetime.now(timezone.utc)

    def _order(self, buyer_user_id, order_id, seller_tenant_id=None, lock=False):
        q=select(MarketplaceOrder).where(MarketplaceOrder.id==order_id)
        if buyer_user_id is not None: q=q.where(MarketplaceOrder.buyer_user_id==buyer_user_id)
        if seller_tenant_id is not None: q=q.where(MarketplaceOrder.seller_tenant_id==seller_tenant_id)
        if lock:q=q.with_for_update()
        x=self.db.scalar(q)
        if not x: raise MarketplaceError('marketplace order not found')
        return x

    def create_payment_session(self, buyer_user_id:str, customer_order_id:int, provider:str):
        co=self.db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.id==customer_order_id, MarketplaceCustomerOrder.buyer_user_id==buyer_user_id).with_for_update())
        if not co: raise MarketplaceError('customer order not found')
        if co.status!='pending_payment': raise MarketplaceError('customer order is not awaiting payment')
        existing=self.db.scalar(select(MarketplacePaymentSession).where(MarketplacePaymentSession.customer_order_id==co.id))
        if existing: return existing
        children=self.db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id==co.id).order_by(MarketplaceSellerOrder.id)).all()
        if not children: raise MarketplaceError('customer order has no seller orders')
        total=sum((_money(x.total) for x in children),Decimal('0'))
        if _money(total)!=_money(co.total): raise MarketplaceError('seller order totals do not reconcile with customer order')
        session=MarketplacePaymentSession(customer_order_id=co.id,buyer_user_id=buyer_user_id,reference=f'HUS-PAY:{co.reference}',provider=provider,amount=_money(co.total),currency=co.currency,status='pending')
        self.db.add(session); self.db.flush()
        for so in children:
            mo=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==so.marketplace_order_id).with_for_update())
            if not mo or mo.currency!=co.currency or _money(mo.total)!=_money(so.total): raise MarketplaceError('seller order payment allocation mismatch')
            ref=f'{session.reference}:{so.id}'
            self.db.add(MarketplacePaymentAllocation(session_id=session.id,seller_order_id=so.id,marketplace_order_id=mo.id,seller_tenant_id=so.seller_tenant_id,amount=_money(so.total),currency=co.currency,payment_reference=ref))
        self.db.flush(); self.assert_payment_conservation(session.id)
        self.db.commit(); self.db.refresh(session); return session

    def assert_payment_conservation(self, session_id: int):
        """Validate customer payment session against its immutable seller allocations.

        This boundary prevents the charged customer amount from drifting away from
        the seller-order amounts that the marketplace intends to settle.
        """
        session = self.db.get(MarketplacePaymentSession, session_id)
        if not session:
            raise MarketplaceError("payment session not found")
        co = self.db.get(MarketplaceCustomerOrder, session.customer_order_id)
        if not co:
            raise MarketplaceError("payment session customer order not found")
        allocations = self.db.scalars(
            select(MarketplacePaymentAllocation)
            .where(MarketplacePaymentAllocation.session_id == session.id)
            .order_by(MarketplacePaymentAllocation.id)
        ).all()
        if not allocations:
            raise MarketplaceError("payment session has no allocations")
        allocation_total = sum((_money(x.amount) for x in allocations), Decimal('0'))
        checks = {
            "session_currency_matches_customer": session.currency == co.currency,
            "session_amount_matches_customer": _money(session.amount) == _money(co.total),
            "allocation_total_matches_session": allocation_total == _money(session.amount),
            "allocation_currency_matches_session": all(x.currency == session.currency for x in allocations),
        }
        for allocation in allocations:
            so = self.db.get(MarketplaceSellerOrder, allocation.seller_order_id)
            mo = self.db.get(MarketplaceOrder, allocation.marketplace_order_id)
            checks[f"allocation_{allocation.id}_seller_order"] = bool(so and so.customer_order_id == co.id and so.marketplace_order_id == mo.id)
            checks[f"allocation_{allocation.id}_amount"] = bool(so and mo and _money(allocation.amount) == _money(so.total) == _money(mo.total))
            checks[f"allocation_{allocation.id}_currency"] = bool(so and mo and mo.currency == session.currency and allocation.currency == mo.currency)
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise MarketplaceError("payment conservation violation: " + ", ".join(failed))
        return {"session_id": session.id, "currency": session.currency, "amount": str(_money(session.amount)), "checks": checks}

    def capture_payment_session(self, buyer_user_id:str, customer_order_id:int, provider_payment_id:str):
        if not provider_payment_id: raise MarketplaceError('provider payment id required')
        session=self.db.scalar(select(MarketplacePaymentSession).where(MarketplacePaymentSession.customer_order_id==customer_order_id,MarketplacePaymentSession.buyer_user_id==buyer_user_id).with_for_update())
        if not session: raise MarketplaceError('payment session not found')
        if session.status=='captured':
            if session.provider_payment_id==provider_payment_id: return session
            raise MarketplaceError('payment session already captured with a different provider payment id')
        if session.status!='pending': raise MarketplaceError('payment session is not capturable')
        allocations=self.db.scalars(select(MarketplacePaymentAllocation).where(MarketplacePaymentAllocation.session_id==session.id).order_by(MarketplacePaymentAllocation.id)).all()
        if not allocations: raise MarketplaceError('payment session has no allocations')
        self.assert_payment_conservation(session.id)
        from app.engines.payments import PaymentProductionService
        payment_service=PaymentProductionService(self.db)
        capture_date = datetime.now(timezone.utc).date()
        for a in allocations:
            mo=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==a.marketplace_order_id).with_for_update())
            so=self.db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.id==a.seller_order_id).with_for_update())
            if not mo or not so: raise MarketplaceError('payment allocation order not found')
            p=payment_service.create_intent(a.seller_tenant_id,a.payment_reference,session.provider,a.amount,a.currency,market_id=mo.market_id,commit=False)
            p.provider_payment_id=f'{provider_payment_id}:{a.id}'
            p.status='authorized'
            p.updated_at=datetime.now(timezone.utc)
            payment_service.capture_verified(a.seller_tenant_id, a.payment_reference,
                                             posting_date=capture_date, commit=False)
            mo.status='paid'; mo.payment_reference=a.payment_reference; mo.updated_at=datetime.now(timezone.utc)
            so.status='paid'; so.updated_at=datetime.now(timezone.utc)
            payout=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==mo.id).with_for_update())
            if payout: payout.payment_reference=a.payment_reference
            self.assert_financial_invariants(mo.id)
            self._event(a.seller_tenant_id,'marketplace.order.paid','marketplace_order',mo.id,{'payment_session':session.reference,'provider_payment_id':provider_payment_id})
        session.status='captured'; session.provider_payment_id=provider_payment_id; session.updated_at=datetime.now(timezone.utc)
        co=self.db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.id==session.customer_order_id).with_for_update())
        if co: co.status='paid'; co.updated_at=datetime.now(timezone.utc)
        self.db.commit(); self.db.refresh(session); return session

    def attach_payment_intent(self,buyer_user_id:str, order_id:int, provider:str):
        o=self._order(buyer_user_id,order_id,lock=True)
        if o.status!='pending_payment': raise MarketplaceError('order is not awaiting payment')
        if o.payment_reference: raise MarketplaceError('payment intent already exists for order')
        ref=f'MKT-PAY:{o.reference}'
        from app.engines.payments import PaymentProductionService
        p=PaymentProductionService(self.db).create_intent(o.seller_tenant_id,ref,provider,Decimal(str(o.total)),o.currency,market_id=o.market_id)
        o.payment_reference=p.reference; self.db.commit(); self.db.refresh(o)
        return p

    def mark_paid(self,seller_tenant_id:int, order_id:int, payment_reference:str):
        o=self._order(None,order_id,seller_tenant_id,True)
        if o.status!='pending_payment': raise MarketplaceError('order is not awaiting payment')
        p=self.db.scalar(select(PaymentIntent).where(PaymentIntent.tenant_id==seller_tenant_id,PaymentIntent.reference==payment_reference))
        if not p or p.status!='captured': raise MarketplaceError('payment must be captured before marketplace order is paid')
        if p.currency!=o.currency or _money(p.amount)!=_money(o.total): raise MarketplaceError('captured payment does not match marketplace order')
        try:
            payment_metadata=json.loads(p.metadata_json or '{}')
        except (TypeError, ValueError):
            payment_metadata={}
        if payment_metadata.get('market_id') is None or int(payment_metadata['market_id']) != o.market_id:
            raise MarketplaceError('payment market does not match marketplace order')
        o.status='paid'; o.payment_reference=payment_reference; o.updated_at=datetime.now(timezone.utc)
        payout=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id).with_for_update())
        if payout: payout.payment_reference=payment_reference
        so=self.db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==o.id))
        if so: so.status='paid'; so.updated_at=datetime.now(timezone.utc)
        self._sync_customer_order(o.customer_order_id)
        self.assert_financial_invariants(o.id)
        payout_for_audit = self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
        if payout_for_audit:
            self.assert_seller_balance_conservation(payout_for_audit)
        self._event(seller_tenant_id,'marketplace.order.paid','marketplace_order',o.id,{'payment_reference':payment_reference}); self.db.commit(); return o

    def mark_processing(self,seller_tenant_id:int,order_id:int):
        o=self._order(None,order_id,seller_tenant_id,True)
        if o.status!='paid': raise MarketplaceError('only paid orders can enter processing')
        o.status='processing'; o.updated_at=datetime.now(timezone.utc)
        so=self.db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==o.id))
        if so: so.status='processing'; so.updated_at=datetime.now(timezone.utc)
        self._sync_customer_order(o.customer_order_id); self._event(seller_tenant_id,'marketplace.order.processing','marketplace_order',o.id,{}); self.db.commit(); return o

    def mark_shipped(self,seller_tenant_id:int,order_id:int,shipment_id:int):
        o=self._order(None,order_id,seller_tenant_id,True)
        if o.status not in {'paid','processing'}: raise MarketplaceError('order cannot be marked shipped from current status')
        if not o.sales_order_id: raise MarketplaceError('service order has no shipment linkage')
        s=self.db.scalar(select(Shipment).where(Shipment.id==shipment_id,Shipment.tenant_id==seller_tenant_id,Shipment.order_id==o.sales_order_id))
        if not s: raise MarketplaceError('shipment does not belong to marketplace order')
        if s.status not in {'picked_up','in_transit','out_for_delivery','delivered'}: raise MarketplaceError('shipment is not in transit')
        o.status='delivered' if s.status=='delivered' else 'shipped'; o.updated_at=datetime.now(timezone.utc); self._event(seller_tenant_id,'marketplace.order.shipped','marketplace_order',o.id,{'shipment_id':shipment_id,'shipment_status':s.status}); self.db.commit(); return o

    def mark_delivered(self,seller_tenant_id:int,order_id:int,shipment_id:int):
        o=self._order(None,order_id,seller_tenant_id,True)
        if not o.sales_order_id: raise MarketplaceError('service order has no shipment')
        s=self.db.scalar(select(Shipment).where(Shipment.id==shipment_id,Shipment.tenant_id==seller_tenant_id,Shipment.order_id==o.sales_order_id,Shipment.status=='delivered'))
        if not s: raise MarketplaceError('delivered shipment not found')
        if o.status not in {'shipped','delivered'}: raise MarketplaceError('order is not in delivery state')
        o.status='completed'; o.updated_at=datetime.now(timezone.utc)
        so=self.db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.marketplace_order_id==o.id))
        if so: so.status='fulfilled'; so.updated_at=datetime.now(timezone.utc)
        self._sync_customer_order(o.customer_order_id)
        p=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id, MarketplacePayout.seller_tenant_id==seller_tenant_id).with_for_update())
        if p and p.status=='held' and p.settlement_reference: p.status='eligible'; p.eligible_at=datetime.now(timezone.utc)
        self._event(seller_tenant_id,'marketplace.order.completed','marketplace_order',o.id,{'shipment_id':shipment_id}); self.db.commit(); return o

    def cancel(self,buyer_user_id,order_id):
        o=self._order(buyer_user_id,order_id,lock=True)
        if o.status != 'pending_payment': raise MarketplaceError('paid or processing orders require dispute/refund workflow; direct cancellation is not allowed')
        if o.sales_order_id:
            CommerceProductionService(self.db).cancel(o.seller_tenant_id,o.sales_order_id)
        o.status='cancelled'; o.updated_at=datetime.now(timezone.utc)
        p=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id))
        if p: p.status='reversed'
        self._event(o.seller_tenant_id,'marketplace.order.cancelled','marketplace_order',o.id,{}); self.db.commit(); return o

    def settle_order_payment(self, seller_tenant_id:int, order_id:int, settlement_reference:str):
        o=self._order(None,order_id,seller_tenant_id,True)
        if o.status not in {'paid','processing','shipped','delivered','completed'}:
            raise MarketplaceError('order payment is not eligible for settlement')
        if not o.payment_reference:
            raise MarketplaceError('order has no payment reference')
        settlement=self.db.scalar(select(PaymentSettlement).where(
            PaymentSettlement.tenant_id==seller_tenant_id,
            PaymentSettlement.payment_reference==o.payment_reference,
            PaymentSettlement.settlement_reference==settlement_reference,
            PaymentSettlement.status=='settled'))
        if not settlement:
            raise MarketplaceError('verified settled payment not found for order')
        if settlement.currency != o.currency or _money(settlement.amount) != _money(o.total):
            raise MarketplaceError('settlement does not match marketplace order')
        if settlement.market_id is None or settlement.market_id != o.market_id:
            raise MarketplaceError('settlement market does not match marketplace order')
        if settlement.reconciliation_status != 'reconciled':
            raise MarketplaceError('settlement reconciliation is not closed')
        if settlement.provider != self.db.scalar(select(PaymentIntent.provider).where(
                PaymentIntent.tenant_id == seller_tenant_id,
                PaymentIntent.reference == o.payment_reference)):
            raise MarketplaceError('settlement provider does not match marketplace payment')
        payout=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id, MarketplacePayout.seller_tenant_id==seller_tenant_id).with_for_update())
        if not payout:
            raise MarketplaceError('payout not found')
        if payout.status=='paid':
            return payout
        payout.payment_reference=o.payment_reference
        payout.settlement_reference=settlement_reference
        if o.status=='completed' and payout.status=='held':
            payout.status='eligible'; payout.eligible_at=datetime.now(timezone.utc)
            self._balance_entry(payout,'credit',payout.net_amount,f'settlement:{settlement_reference}')
        self.assert_financial_invariants(o.id)
        payout_for_audit = self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
        if payout_for_audit:
            self.assert_seller_balance_conservation(payout_for_audit)
        self._event(seller_tenant_id,'marketplace.payout.settlement.linked','payout',payout.id,{'order_id':o.id,'payment_reference':o.payment_reference,'settlement_reference':settlement_reference})
        self.db.commit(); return payout

    def seller_statement(self, seller_tenant_id:int, market_id:int, currency:str, from_at=None, to_at=None):
        currency=currency.upper()
        base=select(MarketplaceSellerBalanceEntry).where(
            MarketplaceSellerBalanceEntry.seller_tenant_id==seller_tenant_id,
            MarketplaceSellerBalanceEntry.market_id==market_id,
            MarketplaceSellerBalanceEntry.currency==currency)
        if from_at is not None:
            opening_rows=self.db.scalars(base.where(MarketplaceSellerBalanceEntry.created_at < from_at).order_by(MarketplaceSellerBalanceEntry.id)).all()
        else:
            opening_rows=[]
        def signed(e):
            return _money(e.amount) if e.entry_type=='credit' else -_money(e.amount)
        opening=sum((signed(e) for e in opening_rows), Decimal('0'))
        q=base
        if from_at is not None: q=q.where(MarketplaceSellerBalanceEntry.created_at >= from_at)
        if to_at is not None: q=q.where(MarketplaceSellerBalanceEntry.created_at <= to_at)
        rows=self.db.scalars(q.order_by(MarketplaceSellerBalanceEntry.id)).all()
        running=opening
        items=[]
        for e in rows:
            delta=signed(e); running += delta
            items.append({'id':e.id,'created_at':e.created_at.isoformat(),'entry_type':e.entry_type,'amount':str(_money(e.amount)),'currency':e.currency,'reference':e.reference,'source_reference':e.source_reference,'running_balance':str(running.quantize(Decimal('0.0001')))})
        return {'market_id':market_id,'currency':currency,'from_at':from_at.isoformat() if from_at else None,'to_at':to_at.isoformat() if to_at else None,'opening_balance':str(opening.quantize(Decimal('0.0001'))),'credits':str(sum((_money(e.amount) for e in rows if e.entry_type=='credit'),Decimal('0')).quantize(Decimal('0.0001'))),'refunds':str(sum((_money(e.amount) for e in rows if e.entry_type=='refund_reversal'),Decimal('0')).quantize(Decimal('0.0001'))),'payouts':str(sum((_money(e.amount) for e in rows if e.entry_type=='payout_debit'),Decimal('0')).quantize(Decimal('0.0001'))),'available_balance':str(running.quantize(Decimal('0.0001'))),'items':items}

    def seller_balance(self, seller_tenant_id:int, market_id:int|None=None, currency:str|None=None):
        q=select(MarketplaceSellerBalanceEntry).where(MarketplaceSellerBalanceEntry.seller_tenant_id==seller_tenant_id)
        if market_id is not None: q=q.where(MarketplaceSellerBalanceEntry.market_id==market_id)
        if currency is not None: q=q.where(MarketplaceSellerBalanceEntry.currency==currency.upper())
        entries=self.db.scalars(q.order_by(MarketplaceSellerBalanceEntry.id)).all()
        by_currency={}
        for e in entries:
            sign=Decimal('1') if e.entry_type=='credit' else Decimal('-1')
            by_currency[e.currency]=by_currency.get(e.currency,Decimal('0')) + sign*_money(e.amount)
        return {k:str(v) for k,v in by_currency.items()}

    def _balance_entry(self, payout, entry_type, amount, source_reference):
        amount=_money(amount)
        if amount <= 0: return None
        existing=self.db.scalar(select(MarketplaceSellerBalanceEntry).where(
            MarketplaceSellerBalanceEntry.marketplace_payout_id==payout.id,
            MarketplaceSellerBalanceEntry.entry_type==entry_type,
            MarketplaceSellerBalanceEntry.source_reference==source_reference))
        if existing: return existing
        prefix='CREDIT' if entry_type=='credit' else ('PAYOUT' if entry_type=='payout_debit' else ('REFUND-RECOVERY' if entry_type=='refund_recovery' else 'REFUND'))
        x=MarketplaceSellerBalanceEntry(
            market_id=payout.market_id, seller_tenant_id=payout.seller_tenant_id,
            marketplace_payout_id=payout.id, entry_type=entry_type, amount=amount,
            currency=payout.currency, reference=f'SBAL:{prefix}:{payout.reference}:{uuid4().hex[:12].upper()}',
            source_reference=source_reference)
        self.db.add(x); self.db.flush(); return x

    def _available_balance_amount(self, seller_tenant_id, market_id, currency):
        entries=self.db.scalars(select(MarketplaceSellerBalanceEntry).where(
            MarketplaceSellerBalanceEntry.seller_tenant_id==seller_tenant_id,
            MarketplaceSellerBalanceEntry.market_id==market_id,
            MarketplaceSellerBalanceEntry.currency==currency)).all()
        total=Decimal('0')
        for e in entries: total += _money(e.amount) if e.entry_type=='credit' else -_money(e.amount)
        return total

    def payout_eligible(self,seller_tenant_id:int,order_id:int):
        p=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==order_id,MarketplacePayout.seller_tenant_id==seller_tenant_id).with_for_update())
        if not p: raise MarketplaceError('payout not found')
        o=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==order_id,MarketplaceOrder.seller_tenant_id==seller_tenant_id).with_for_update())
        if not o: raise MarketplaceError('marketplace order not found')
        if p.market_id is None or o.market_id is None or o.market_id != p.market_id: raise MarketplaceError('payout market mismatch')
        if p.currency != o.currency: raise MarketplaceError('payout currency mismatch')
        if o.status in {'refunded','partially_refunded','disputed'}: raise MarketplaceError('payout is blocked by order financial state')
        if p.status!='eligible': raise MarketplaceError('payout is not eligible')
        return p

    def request_payout(self,seller_tenant_id:int,order_id:int):
        p=self.payout_eligible(seller_tenant_id,order_id)
        destination=self.db.scalar(select(MarketplacePayoutDestination).where(MarketplacePayoutDestination.seller_tenant_id==seller_tenant_id).with_for_update())
        if not destination or destination.status!='verified':
            raise MarketplaceError('verified payout destination is required')
        if not p.market_id:
            raise MarketplaceError('market context is required for payout')
        from app.engines.payment_adapters import evaluate_provider_production_gate
        gate=evaluate_provider_production_gate(self.db, destination.provider, p.market_id, 'payout', currency=p.currency)
        if not gate.allowed:
            raise MarketplaceError('payout provider production gate blocked: ' + ';'.join(gate.blocked_reasons))
        if p.status=='processing' and p.payout_reference:
            return p
        if p.status!='eligible':
            raise MarketplaceError('payout is not eligible')
        p.status='processing'
        p.payout_provider=destination.provider
        p.payout_destination_reference=destination.external_reference
        p.payout_reference=f'PAYOUT-REQ:{p.reference}:{uuid4().hex[:12].upper()}'
        p.requested_at=datetime.now(timezone.utc)
        self._event(seller_tenant_id,'marketplace.payout.requested','payout',p.id,{'payout_reference':p.payout_reference,'provider':destination.provider,'destination_reference':destination.external_reference,'amount':str(p.net_amount),'currency':p.currency})
        self.db.commit(); return p

    def mark_payout_paid(self,seller_tenant_id:int,order_id:int,external_reference:str):
        # Serialize seller-level balance consumption so concurrent payouts cannot
        # both observe the same available balance and overdraw the seller.
        seller_lock=self.db.scalar(select(Tenant).where(Tenant.id==seller_tenant_id).with_for_update())
        if not seller_lock: raise MarketplaceError('seller tenant not found')
        p=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==order_id,MarketplacePayout.seller_tenant_id==seller_tenant_id).with_for_update())
        if not p: raise MarketplaceError('payout not found')
        o=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==order_id,MarketplaceOrder.seller_tenant_id==seller_tenant_id).with_for_update())
        if not o: raise MarketplaceError('marketplace order not found')
        if p.market_id is None or o.market_id is None or o.market_id != p.market_id: raise MarketplaceError('payout market mismatch')
        if p.currency != o.currency: raise MarketplaceError('payout currency mismatch')
        if o.status in {'refunded','partially_refunded','disputed'}: raise MarketplaceError('payout is blocked by order financial state')
        if p.status=='paid':
            if p.external_reference != external_reference:
                raise MarketplaceError('payout already completed with a different external reference')
            return p
        if p.status!='processing': raise MarketplaceError('payout request must be created before payment completion')
        if not p.payment_reference or not p.settlement_reference:
            raise MarketplaceError('payout requires a linked settled payment')
        destination=self.db.scalar(select(MarketplacePayoutDestination).where(MarketplacePayoutDestination.seller_tenant_id==seller_tenant_id))
        if not destination or destination.status!='verified': raise MarketplaceError('verified payout destination is required')
        if destination.provider != p.payout_provider or destination.external_reference != p.payout_destination_reference:
            raise MarketplaceError('payout destination changed after payout request')
        if not external_reference: raise MarketplaceError('external payout reference required')
        from app.engines.payment_adapters import evaluate_provider_production_gate
        gate=evaluate_provider_production_gate(self.db, p.payout_provider, p.market_id, 'payout', currency=p.currency)
        if not gate.allowed:
            raise MarketplaceError('payout provider production gate blocked: ' + ';'.join(gate.blocked_reasons))
        conflict=self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.external_reference==external_reference, MarketplacePayout.id!=p.id))
        if conflict: raise MarketplaceError('external payout reference already used')
        available=self._available_balance_amount(seller_tenant_id,p.market_id,p.currency)
        if available < _money(p.net_amount):
            raise MarketplaceError('seller available balance is insufficient')
        self._balance_entry(p,'payout_debit',p.net_amount,p.payout_reference or external_reference)
        p.external_reference=external_reference; p.status='paid'; p.paid_at=datetime.now(timezone.utc)
        self.assert_financial_invariants(o.id)
        payout_for_audit = self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == o.id))
        if payout_for_audit:
            self.assert_seller_balance_conservation(payout_for_audit)
        self._event(seller_tenant_id,'marketplace.payout.paid','payout',p.id,{'external_reference':external_reference,'amount':str(p.net_amount),'currency':p.currency,'settlement_reference':p.settlement_reference})
        self.db.commit(); return p

    def create_review(self,buyer_user_id,order_id,listing_id,rating,title='',body=''):
        o=self._order(buyer_user_id,order_id)
        if o.status!='completed': raise MarketplaceError('review is available after completed order')
        line=self.db.scalar(select(MarketplaceOrderLine).where(MarketplaceOrderLine.marketplace_order_id==o.id,MarketplaceOrderLine.listing_id==listing_id))
        if not line: raise MarketplaceError('listing was not part of order')
        if self.db.scalar(select(MarketplaceReview).where(MarketplaceReview.marketplace_order_id==o.id,MarketplaceReview.listing_id==listing_id,MarketplaceReview.buyer_user_id==buyer_user_id)): raise MarketplaceError('review already exists')
        if rating<1 or rating>5: raise MarketplaceError('rating must be 1..5')
        x=MarketplaceReview(marketplace_order_id=o.id,listing_id=listing_id,buyer_user_id=buyer_user_id,rating=rating,title=title or '',body=body or '',status='published'); self.db.add(x); self._event(o.seller_tenant_id,'marketplace.review.created','review',x.id,{'listing_id':listing_id,'rating':rating}); self.db.commit(); return x

    def open_dispute(self,buyer_user_id,order_id,reason,description):
        o=self._order(buyer_user_id,order_id,lock=True)
        if o.status not in {'paid','processing','shipped','delivered','completed'}: raise MarketplaceError('order cannot be disputed in current status')
        if self.db.scalar(select(MarketplaceDispute).where(MarketplaceDispute.marketplace_order_id==o.id)): raise MarketplaceError('order already has a dispute')
        x=MarketplaceDispute(market_id=o.market_id,marketplace_order_id=o.id,opened_by_user_id=buyer_user_id,reason=reason,description=description,status='open'); self.db.add(x); o.status='disputed'; self._event(o.seller_tenant_id,'marketplace.dispute.opened','dispute',x.id,{'order_id':o.id,'reason':reason}); self.db.commit(); return x
