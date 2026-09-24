from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from sqlalchemy import select, func

from app.core.models.marketplace import MarketplaceListing, MarketplaceOrder, MarketplaceDispute, MarketplaceReturnRequest
from app.core.models.marketplace_operational import MarketplaceDiscountAllocation, MarketplaceRepricingJob
from app.core.models.marketplace_growth import MarketplacePricingRule, MarketplacePromotion, MarketplacePromotionItem, MarketplaceAdCampaign, MarketplaceAdGroup, MarketplaceB2BPrice, MarketplaceCustomerCase, MarketplaceIntegrationApp
from app.core.models.platform_completion import (
    MarketplaceCoupon, MarketplaceCouponRedemption, MarketplacePriceDecision,
    MarketplaceAdEvent, MarketplaceAdCharge, MarketplaceAdAttribution,
    MarketplaceCustomerCaseMessage, MarketplaceSellerHealthSnapshot,
    MarketplaceFeedJob, MarketplaceWebhookDelivery, MarketplaceAnalyticsSnapshot,
)

class MarketplaceCompletionError(ValueError):
    pass

def money(v):
    return Decimal(str(v or 0)).quantize(Decimal('0.0001'))

class MarketplaceCompletionService:
    def __init__(self, db):
        self.db = db

    def evaluate_price(self, seller_tenant_id, listing_id, source='rule'):
        listing = self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id == listing_id, MarketplaceListing.seller_tenant_id == seller_tenant_id))
        if not listing:
            raise MarketplaceCompletionError('listing not found for seller')
        rules = self.db.scalars(select(MarketplacePricingRule).where(MarketplacePricingRule.seller_tenant_id == seller_tenant_id, MarketplacePricingRule.active.is_(True)).order_by(MarketplacePricingRule.priority, MarketplacePricingRule.id)).all()
        if not rules:
            return {'listing_id': listing.id, 'price': str(money(listing.unit_price)), 'decision_id': None, 'status': 'unchanged'}
        price = money(listing.unit_price)
        chosen = None
        proposed = price
        reason = 'no applicable action'
        for rule in rules:
            scope = rule.scope_json or {}
            if scope.get('listing_id') not in (None, '*', listing.id, str(listing.id)) and scope.get('listing_id') != listing.id:
                continue
            action = rule.action_json or {}
            kind = action.get('type', 'floor')
            if kind in {'set_price', 'fixed'} and action.get('price') is not None:
                proposed = money(action['price'])
                chosen = rule; reason = 'pricing rule fixed price'; break
            if kind in {'percent_adjust', 'percentage'} and action.get('bps') is not None:
                proposed = money(price * (Decimal(10000) + Decimal(int(action['bps']))) / Decimal(10000))
                chosen = rule; reason = 'pricing rule percentage adjustment'; break
            if kind == 'floor' and rule.min_price is not None:
                proposed = max(proposed, money(rule.min_price)); chosen = rule; reason = 'pricing rule floor'
                break
        if chosen is not None:
            if chosen.min_price is not None: proposed = max(proposed, money(chosen.min_price))
            if chosen.max_price is not None: proposed = min(proposed, money(chosen.max_price))
        proposed = max(Decimal('0'), proposed)
        decision = MarketplacePriceDecision(seller_tenant_id=seller_tenant_id, listing_id=listing.id, source=source, previous_price=price, proposed_price=proposed, floor_price=money(chosen.min_price) if chosen and chosen.min_price is not None else None, ceiling_price=money(chosen.max_price) if chosen and chosen.max_price is not None else None, rule_id=chosen.id if chosen else None, reason=reason, status='accepted')
        self.db.add(decision)
        if proposed != price:
            listing.unit_price = proposed
            listing.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(decision)
        return {'listing_id': listing.id, 'price': str(proposed), 'previous_price': str(price), 'decision_id': decision.id, 'status': 'changed' if proposed != price else 'unchanged'}

    def create_coupon(self, seller_tenant_id, code, kind, value, starts_at, ends_at, currency=None, minimum_subtotal=0, max_redemptions=None, per_buyer_limit=1):
        if ends_at <= starts_at: raise MarketplaceCompletionError('coupon end must be after start')
        if kind == 'percentage' and money(value) > Decimal('100'): raise MarketplaceCompletionError('percentage coupon cannot exceed 100')
        if kind not in {'percentage','fixed'}: raise MarketplaceCompletionError('unsupported coupon kind')
        x = MarketplaceCoupon(seller_tenant_id=seller_tenant_id, code=code.strip().upper(), kind=kind, value=money(value), currency=currency, minimum_subtotal=money(minimum_subtotal), max_redemptions=max_redemptions, per_buyer_limit=per_buyer_limit, starts_at=starts_at, ends_at=ends_at, active=True)
        self.db.add(x); self.db.commit(); self.db.refresh(x); return x

    def preview_promotion(self, seller_tenant_id, listing_id, subtotal, now=None):
        now = now or datetime.now(timezone.utc); subtotal = money(subtotal)
        rows = self.db.execute(select(MarketplacePromotion, MarketplacePromotionItem).join(MarketplacePromotionItem, MarketplacePromotionItem.promotion_id == MarketplacePromotion.id).where(MarketplacePromotion.seller_tenant_id == seller_tenant_id, MarketplacePromotionItem.listing_id == listing_id)).all()
        # status/window are authoritative; this intentionally does not trust a client-provided discount.
        best = Decimal('0'); chosen = None
        for p, _ in rows:
            starts = p.starts_at.replace(tzinfo=timezone.utc) if p.starts_at.tzinfo is None else p.starts_at
            ends = p.ends_at.replace(tzinfo=timezone.utc) if p.ends_at.tzinfo is None else p.ends_at
            if p.status not in {'scheduled','active'} or not (starts <= now <= ends): continue
            cfg = p.config_json or {}
            if p.kind in {'percentage_off','percent_off'}:
                d = (subtotal * Decimal(str(cfg.get('percent', cfg.get('discount_percent', 0)))) / Decimal('100')).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            elif p.kind == 'fixed_amount':
                d = money(cfg.get('amount', 0))
            else:
                continue
            d = min(subtotal, max(Decimal('0'), d))
            if d > best: best, chosen = d, p
        return {'promotion_id': chosen.id if chosen else None, 'discount': str(best), 'subtotal_after': str(subtotal - best)}

    def redeem_coupon(self, buyer_user_id, marketplace_order_id, code, subtotal, currency, now=None):
        from app.core.models.marketplace import MarketplaceOrder
        order = self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id == marketplace_order_id, MarketplaceOrder.buyer_user_id == buyer_user_id).with_for_update())
        if not order: raise MarketplaceCompletionError('order does not belong to buyer')
        if order.status != 'pending_payment': raise MarketplaceCompletionError('coupon can only be redeemed before payment')
        authoritative_subtotal = money(order.subtotal)
        authoritative_currency = order.currency.upper()
        if money(subtotal) != authoritative_subtotal: raise MarketplaceCompletionError('coupon subtotal does not match order')
        if currency.upper() != authoritative_currency: raise MarketplaceCompletionError('coupon currency does not match order')
        subtotal = authoritative_subtotal; currency = authoritative_currency
        now = now or datetime.now(timezone.utc)
        coupon = self.db.scalar(select(MarketplaceCoupon).where(MarketplaceCoupon.code == code.strip().upper(), MarketplaceCoupon.active.is_(True)))
        if not coupon: raise MarketplaceCompletionError('coupon not found or inactive')
        starts = coupon.starts_at.replace(tzinfo=timezone.utc) if coupon.starts_at.tzinfo is None else coupon.starts_at
        ends = coupon.ends_at.replace(tzinfo=timezone.utc) if coupon.ends_at.tzinfo is None else coupon.ends_at
        if not starts <= now <= ends: raise MarketplaceCompletionError('coupon is outside its active window')
        if coupon.currency and coupon.currency.upper() != currency.upper(): raise MarketplaceCompletionError('coupon currency mismatch')
        if subtotal < money(coupon.minimum_subtotal): raise MarketplaceCompletionError('order subtotal is below coupon minimum')
        used = self.db.scalar(select(func.count()).select_from(MarketplaceCouponRedemption).where(MarketplaceCouponRedemption.coupon_id == coupon.id)) or 0
        buyer_used = self.db.scalar(select(func.count()).select_from(MarketplaceCouponRedemption).where(MarketplaceCouponRedemption.coupon_id == coupon.id, MarketplaceCouponRedemption.buyer_user_id == buyer_user_id)) or 0
        if coupon.max_redemptions is not None and used >= coupon.max_redemptions: raise MarketplaceCompletionError('coupon redemption limit reached')
        if buyer_used >= coupon.per_buyer_limit: raise MarketplaceCompletionError('buyer coupon limit reached')
        discount = subtotal * coupon.value / Decimal('100') if coupon.kind == 'percentage' else coupon.value
        discount = min(subtotal, max(Decimal('0'), money(discount)))
        x = MarketplaceCouponRedemption(coupon_id=coupon.id, buyer_user_id=buyer_user_id, marketplace_order_id=marketplace_order_id, discount_amount=discount, currency=currency)
        self.db.add(x); self.db.commit(); self.db.refresh(x)
        return {'coupon_id': coupon.id, 'code': coupon.code, 'discount': str(discount), 'currency': currency, 'redemption_id': x.id}

    def ad_event(self, seller_tenant_id, campaign_id, event_type, listing_id=None, ad_group_id=None, buyer_user_id=None, currency=None, bid=None, attribution_key=None, metadata=None):
        campaign = self.db.scalar(select(MarketplaceAdCampaign).where(MarketplaceAdCampaign.id == campaign_id, MarketplaceAdCampaign.seller_tenant_id == seller_tenant_id))
        if not campaign: raise MarketplaceCompletionError('campaign not found for seller')
        if campaign.status not in {'active','scheduled'}: raise MarketplaceCompletionError('campaign is not active')
        currency = (currency or '').strip().upper()
        if not currency: raise MarketplaceCompletionError('currency is required for ad charges')
        cost = Decimal('0')
        if event_type == 'click': cost = money(bid if bid is not None else 0)
        ev = MarketplaceAdEvent(campaign_id=campaign_id, ad_group_id=ad_group_id, listing_id=listing_id, buyer_user_id=buyer_user_id, event_type=event_type, cost=cost, attribution_key=attribution_key, metadata_json=metadata or {})
        self.db.add(ev); self.db.flush()
        if cost:
            spent = self.db.scalar(select(func.coalesce(func.sum(MarketplaceAdEvent.cost), 0)).where(MarketplaceAdEvent.campaign_id == campaign_id, MarketplaceAdEvent.event_type == 'click')) or 0
            if money(spent) > money(campaign.budget_daily):
                self.db.rollback(); raise MarketplaceCompletionError('campaign daily budget exceeded')
            self.db.add(MarketplaceAdCharge(campaign_id=campaign_id, event_id=ev.id, seller_tenant_id=seller_tenant_id, amount=cost, currency=currency, status='pending'))
        self.db.commit(); self.db.refresh(ev)
        return {'event_id': ev.id, 'event_type': event_type, 'cost': str(cost)}

    def attribute_ad_conversion(self, seller_tenant_id, campaign_id, order_id, revenue, listing_id=None):
        campaign = self.db.scalar(select(MarketplaceAdCampaign).where(MarketplaceAdCampaign.id == campaign_id, MarketplaceAdCampaign.seller_tenant_id == seller_tenant_id))
        if not campaign: raise MarketplaceCompletionError('campaign not found for seller')
        existing = self.db.scalar(select(MarketplaceAdAttribution).where(MarketplaceAdAttribution.campaign_id == campaign_id, MarketplaceAdAttribution.order_id == order_id))
        if existing: return existing
        x = MarketplaceAdAttribution(campaign_id=campaign_id, order_id=order_id, listing_id=listing_id, attributed_revenue=money(revenue), attribution_model='last_touch')
        self.db.add(x); self.db.commit(); self.db.refresh(x); return x

    def add_case_message(self, case_id, sender_user_id, sender_role, body, internal=False, seller_tenant_id=None):
        case = self.db.get(MarketplaceCustomerCase, case_id)
        if not case: raise MarketplaceCompletionError('case not found')
        if seller_tenant_id is not None and case.seller_tenant_id != seller_tenant_id:
            raise MarketplaceCompletionError('case does not belong to seller')
        if case.status in {'closed','resolved'}: raise MarketplaceCompletionError('case is closed')
        x = MarketplaceCustomerCaseMessage(case_id=case_id, sender_user_id=sender_user_id, sender_role=sender_role, body=body, internal=internal)
        self.db.add(x); case.updated_at = datetime.now(timezone.utc); self.db.commit(); self.db.refresh(x); return x

    def health_snapshot(self, seller_tenant_id, period_start, period_end):
        orders = self.db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id == seller_tenant_id, MarketplaceOrder.created_at >= period_start, MarketplaceOrder.created_at <= period_end)).all()
        disputes = self.db.scalar(select(func.count()).select_from(MarketplaceDispute).join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceDispute.marketplace_order_id).where(MarketplaceOrder.seller_tenant_id == seller_tenant_id, MarketplaceDispute.created_at >= period_start, MarketplaceDispute.created_at <= period_end)) or 0
        returns = self.db.scalar(select(func.count()).select_from(MarketplaceReturnRequest).join(MarketplaceOrder, MarketplaceOrder.id == MarketplaceReturnRequest.marketplace_order_id).where(MarketplaceOrder.seller_tenant_id == seller_tenant_id, MarketplaceReturnRequest.created_at >= period_start, MarketplaceReturnRequest.created_at <= period_end)) or 0
        cancelled = sum(1 for o in orders if o.status == 'cancelled')
        n = len(orders)
        cancellation_rate = (Decimal(cancelled) / Decimal(n)) if n else Decimal('0')
        dispute_rate = (Decimal(disputes) / Decimal(n)) if n else Decimal('0')
        defect_rate = min(Decimal('1'), cancellation_rate + dispute_rate)
        status = 'healthy' if defect_rate < Decimal('0.02') else ('at_risk' if defect_rate < Decimal('0.05') else 'critical')
        x = MarketplaceSellerHealthSnapshot(seller_tenant_id=seller_tenant_id, period_start=period_start, period_end=period_end, order_count=n, cancelled_count=cancelled, dispute_count=disputes, return_count=returns, defect_rate=defect_rate, cancellation_rate=cancellation_rate, dispute_rate=dispute_rate, status=status, details_json={'source':'transactional_snapshot'})
        self.db.add(x); self.db.commit(); self.db.refresh(x); return x

    def create_feed(self, tenant_id, feed_type, payload):
        x = MarketplaceFeedJob(tenant_id=tenant_id, feed_type=feed_type, payload_json=payload, status='queued', attempts=0)
        self.db.add(x); self.db.commit(); self.db.refresh(x); return x

    def complete_feed(self, tenant_id, feed_id, success=True, error=None):
        x = self.db.scalar(select(MarketplaceFeedJob).where(MarketplaceFeedJob.id == feed_id, MarketplaceFeedJob.tenant_id == tenant_id))
        if not x: raise MarketplaceCompletionError('feed job not found')
        if x.status in {'completed','failed'}: raise MarketplaceCompletionError('feed job already terminal')
        x.attempts += 1; x.status = 'completed' if success else 'failed'; x.error = error; x.completed_at = datetime.now(timezone.utc)
        self.db.commit(); return x

    def queue_webhook(self, integration_app_id, event_type, event_id, payload, owner_tenant_id=None):
        app = self.db.get(MarketplaceIntegrationApp, integration_app_id)
        if not app or app.status != 'active': raise MarketplaceCompletionError('integration app unavailable')
        if owner_tenant_id is not None and app.owner_tenant_id != owner_tenant_id:
            raise MarketplaceCompletionError('integration app does not belong to seller')
        x = MarketplaceWebhookDelivery(integration_app_id=integration_app_id, event_type=event_type, event_id=event_id, payload_json=payload, status='queued')
        self.db.add(x); self.db.commit(); self.db.refresh(x); return x

    def analytics_snapshot(self, tenant_id, period_start, period_end):
        orders = self.db.scalars(select(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id == tenant_id, MarketplaceOrder.created_at >= period_start, MarketplaceOrder.created_at <= period_end)).all()
        revenue = sum((money(o.total) for o in orders if o.status not in {'cancelled'}), Decimal('0'))
        paid = sum((1 for o in orders if o.status not in {'pending_payment','cancelled'}), 0)
        metrics = [('orders', Decimal(len(orders))), ('revenue', revenue), ('paid_orders', Decimal(paid))]
        created=[]
        for code, value in metrics:
            x=MarketplaceAnalyticsSnapshot(tenant_id=tenant_id,period_start=period_start,period_end=period_end,metric_code=code,value=value,dimensions_json={}); self.db.add(x); created.append(x)
        self.db.commit(); return created
    def allocate_order_discount(self, customer_order_id, allocations, *, promotion_id=None, coupon_id=None, funding_source='seller', currency=None):
        """Persist checkout-authoritative discount funding and propagate its financial effect.

        Discounts are only mutable while the customer order is still awaiting payment.
        The customer charge is reduced by the full discount, while seller proceeds are
        reduced only by the seller-funded portion; platform-funded amounts remain a
        separate payout subsidy snapshot.
        """
        from app.core.models.marketplace import MarketplaceCustomerOrder, MarketplaceSellerOrder, MarketplaceOrder, MarketplaceOrderLine, MarketplacePayout
        from app.core.models.marketplace_operational import MarketplaceOrderFinancialAllocation
        order = self.db.scalar(select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.id == customer_order_id).with_for_update())
        if not order: raise MarketplaceCompletionError('customer order not found')
        if order.status != 'pending_payment': raise MarketplaceCompletionError('discount allocation is locked after payment begins')
        if currency and order.currency.upper() != currency.upper(): raise MarketplaceCompletionError('discount currency mismatch')
        if funding_source not in {'seller','platform','shared'}: raise MarketplaceCompletionError('invalid discount funding source')
        total = Decimal('0'); seen = set(); created = []
        for item in allocations:
            seller_order_id = int(item['seller_order_id']); amount = money(item['amount'])
            if amount < 0: raise MarketplaceCompletionError('discount allocation cannot be negative')
            if funding_source == 'seller':
                seller_funded = amount; platform_funded = Decimal('0')
            elif funding_source == 'platform':
                seller_funded = Decimal('0'); platform_funded = amount
            else:
                if 'seller_amount' not in item or 'platform_amount' not in item:
                    raise MarketplaceCompletionError('shared discount funding requires seller_amount and platform_amount')
                seller_funded = money(item['seller_amount']); platform_funded = money(item['platform_amount'])
                if seller_funded < 0 or platform_funded < 0 or seller_funded + platform_funded != amount:
                    raise MarketplaceCompletionError('shared discount funding must conserve allocation amount')
            if seller_order_id in seen: raise MarketplaceCompletionError('duplicate seller order allocation')
            seen.add(seller_order_id)
            so = self.db.scalar(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.id == seller_order_id, MarketplaceSellerOrder.customer_order_id == customer_order_id).with_for_update())
            if not so: raise MarketplaceCompletionError('seller order does not belong to customer order')
            if amount > money(so.subtotal): raise MarketplaceCompletionError('discount exceeds seller subtotal')
            mo = self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id == so.marketplace_order_id).with_for_update())
            if not mo or mo.customer_order_id != customer_order_id: raise MarketplaceCompletionError('marketplace order does not belong to customer order')
            total += amount
            existing = self.db.scalar(select(MarketplaceDiscountAllocation).where(MarketplaceDiscountAllocation.customer_order_id == customer_order_id, MarketplaceDiscountAllocation.seller_order_id == seller_order_id, MarketplaceDiscountAllocation.promotion_id == promotion_id, MarketplaceDiscountAllocation.coupon_id == coupon_id))
            if existing:
                if money(existing.amount) != amount or money(existing.seller_funded_amount or 0) != seller_funded or money(existing.platform_funded_amount or 0) != platform_funded:
                    raise MarketplaceCompletionError('discount allocation already exists with different funding')
                created.append(existing); continue
            x=MarketplaceDiscountAllocation(customer_order_id=customer_order_id,seller_order_id=seller_order_id,seller_tenant_id=so.seller_tenant_id,promotion_id=promotion_id,coupon_id=coupon_id,funding_source=funding_source,amount=amount,seller_funded_amount=seller_funded,platform_funded_amount=platform_funded,currency=order.currency)
            self.db.add(x); self.db.flush(); created.append(x)
            # Customer-facing totals decrease by the full discount. Seller-facing payout
            # proceeds decrease only by the seller-funded component.
            mo.total = money(mo.subtotal) + money(mo.shipping_fee) - amount
            so.total = money(so.subtotal) + money(so.shipping_fee) - amount
            payout = self.db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id == mo.id).with_for_update())
            if payout:
                payout.seller_funded_discount = money(payout.seller_funded_discount) + seller_funded
                payout.platform_funded_discount = money(payout.platform_funded_discount) + platform_funded
                payout.net_amount = money(payout.gross_amount) - money(payout.seller_funded_discount) - money(payout.platform_fee)
            lines = self.db.scalars(select(MarketplaceOrderLine).where(MarketplaceOrderLine.marketplace_order_id == mo.id).order_by(MarketplaceOrderLine.id)).all()
            if lines:
                remaining = seller_funded
                for idx, line in enumerate(lines):
                    alloc = self.db.scalar(select(MarketplaceOrderFinancialAllocation).where(MarketplaceOrderFinancialAllocation.order_line_id == line.id).with_for_update())
                    if not alloc: continue
                    is_last = idx == len(lines) - 1
                    share = remaining if is_last else money(seller_funded * money(line.line_total) / money(mo.subtotal)) if money(mo.subtotal) else Decimal('0')
                    share = money(share); remaining -= share
                    alloc.discount_amount = money(alloc.discount_amount) + share
                    alloc.net_amount = money(alloc.gross_amount) + money(alloc.shipping_amount) - money(alloc.discount_amount) - money(alloc.platform_fee)
        if total > money(order.subtotal): raise MarketplaceCompletionError('discount exceeds customer subtotal')
        # Rebuild customer total from all seller-order totals, preventing partial propagation.
        children=self.db.scalars(select(MarketplaceSellerOrder).where(MarketplaceSellerOrder.customer_order_id==order.id)).all()
        order.total=sum((money(x.total) for x in children), Decimal('0'))
        self.db.commit()
        return {'customer_order_id': customer_order_id, 'discount': str(total.quantize(Decimal('0.0001'))), 'currency': order.currency, 'allocations': [{'seller_order_id': x.seller_order_id, 'seller_tenant_id': x.seller_tenant_id, 'amount': str(x.amount)} for x in created]}

    def schedule_repricing(self, seller_tenant_id, listing_id, run_after, rule_id=None):
        from app.core.models.marketplace import MarketplaceListing
        listing=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id, MarketplaceListing.seller_tenant_id==seller_tenant_id))
        if not listing: raise MarketplaceCompletionError('listing not found for seller')
        if rule_id is not None:
            rule=self.db.scalar(select(MarketplacePricingRule).where(MarketplacePricingRule.id==rule_id, MarketplacePricingRule.seller_tenant_id==seller_tenant_id))
            if not rule: raise MarketplaceCompletionError('pricing rule not found for seller')
        job=MarketplaceRepricingJob(seller_tenant_id=seller_tenant_id,listing_id=listing_id,rule_id=rule_id,run_after=run_after,status='queued')
        self.db.add(job); self.db.commit(); self.db.refresh(job); return job

    def execute_repricing_job(self, seller_tenant_id, job_id):
        job=self.db.scalar(select(MarketplaceRepricingJob).where(MarketplaceRepricingJob.id==job_id, MarketplaceRepricingJob.seller_tenant_id==seller_tenant_id).with_for_update())
        if not job: raise MarketplaceCompletionError('repricing job not found')
        if job.status != 'queued': raise MarketplaceCompletionError('repricing job is not queued')
        job.status='running'; job.attempts += 1; self.db.flush()
        try:
            out=self.evaluate_price(seller_tenant_id, job.listing_id, 'scheduled_rule')
            job.status='completed'; job.completed_at=datetime.now(timezone.utc); job.last_error=None; self.db.commit()
            return {'job_id':job.id,'status':job.status,'price':out['price'],'attempts':job.attempts}
        except Exception as exc:
            self.db.rollback()
            job=self.db.scalar(select(MarketplaceRepricingJob).where(MarketplaceRepricingJob.id==job_id, MarketplaceRepricingJob.seller_tenant_id==seller_tenant_id).with_for_update())
            job.status='failed'; job.last_error=str(exc); job.attempts += 0; job.completed_at=datetime.now(timezone.utc); self.db.commit()
            raise


# Amazon-public capability completion layer. These methods remain part of the same
# unified service and are deliberately deterministic/transactional.
from app.core.models.amazon_completion import *  # noqa: E402,F401,F403

def _promo_checkout(self, seller_tenant_id, customer_order_id, listing_id, subtotal, promotion_ids=None, coupon_id=None, currency=None):
    now=datetime.now(timezone.utc); subtotal=money(subtotal)
    candidates=[]
    rows=self.db.execute(select(MarketplacePromotion, MarketplacePromotionItem).join(MarketplacePromotionItem, MarketplacePromotionItem.promotion_id==MarketplacePromotion.id).where(MarketplacePromotion.seller_tenant_id==seller_tenant_id, MarketplacePromotionItem.listing_id==listing_id)).all()
    allowed=set(promotion_ids or [])
    for p,_ in rows:
        if allowed and p.id not in allowed: continue
        starts=p.starts_at.replace(tzinfo=timezone.utc) if p.starts_at.tzinfo is None else p.starts_at
        ends=p.ends_at.replace(tzinfo=timezone.utc) if p.ends_at.tzinfo is None else p.ends_at
        if p.status not in {'scheduled','active'} or not starts<=now<=ends: continue
        cfg=p.config_json or {}; d=Decimal('0')
        if p.kind in {'percentage_off','percent_off'}: d=money(subtotal*Decimal(str(cfg.get('percent',cfg.get('discount_percent',0))))/100)
        elif p.kind=='fixed_amount': d=money(cfg.get('amount',0))
        candidates.append((p,min(subtotal,max(Decimal('0'),d))))
    candidates.sort(key=lambda x:(x[0].priority if hasattr(x[0],'priority') else 100,x[0].id))
    chosen=[]; total=Decimal('0'); groups=set()
    for p,d in candidates:
        rule=self.db.scalar(select(MarketplacePromotionRule).where(MarketplacePromotionRule.promotion_id==p.id, MarketplacePromotionRule.seller_tenant_id==seller_tenant_id))
        group=rule.stack_group if rule else f'p:{p.id}'
        stackable=rule.stackable if rule else False
        excluded=set(rule.exclusion_codes_json or []) if rule else set()
        if any(c in excluded for c in [q[0].kind for q in chosen]): continue
        if group in groups or (chosen and not stackable): continue
        if d<=0: continue
        if rule and rule.max_discount is not None: d=min(d,money(rule.max_discount))
        d=min(d,subtotal-total); chosen.append((p,d)); groups.add(group); total+=d
    if coupon_id:
        coupon=self.db.get(MarketplaceCoupon,coupon_id)
        if not coupon or coupon.seller_tenant_id!=seller_tenant_id or not coupon.active: raise MarketplaceCompletionError('coupon unavailable')
        if coupon.currency and currency and coupon.currency.upper()!=currency.upper(): raise MarketplaceCompletionError('coupon currency mismatch')
        total_used=self.db.scalar(select(func.coalesce(func.sum(MarketplaceCouponRedemption.discount_amount),0)).where(MarketplaceCouponRedemption.coupon_id==coupon.id)) or 0
        if coupon.max_redemptions is not None and int(self.db.scalar(select(func.count()).select_from(MarketplaceCouponRedemption).where(MarketplaceCouponRedemption.coupon_id==coupon.id)) or 0)>=coupon.max_redemptions: raise MarketplaceCompletionError('coupon redemption limit reached')
        if total_used and money(total_used)>=money(getattr(coupon,'budget_amount',0) or 0) and getattr(coupon,'budget_amount',None): raise MarketplaceCompletionError('coupon budget exhausted')
    return {'subtotal':str(subtotal),'discount':str(total),'subtotal_after':str(subtotal-total),'promotion_ids':[p.id for p,_ in chosen]}

def _record_price_competitor(self, seller_tenant_id, listing_id, source, price, currency):
    listing=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id,MarketplaceListing.seller_tenant_id==seller_tenant_id))
    if not listing: raise MarketplaceCompletionError('listing not found for seller')
    x=MarketplacePriceCompetitor(listing_id=listing_id,source=source,price=money(price),currency=currency); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

def _reprice_against_market(self,seller_tenant_id,listing_id,rule_id=None):
    listing=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id,MarketplaceListing.seller_tenant_id==seller_tenant_id))
    if not listing: raise MarketplaceCompletionError('listing not found')
    q=self.db.scalar(select(MarketplacePriceCompetitor.price).where(MarketplacePriceCompetitor.listing_id==listing_id,MarketplacePriceCompetitor.currency==listing.currency).order_by(MarketplacePriceCompetitor.observed_at.desc()))
    if q is None: return self.evaluate_price(seller_tenant_id,listing_id,'competitive_no_observation')
    rule=self.db.get(MarketplacePricingRule,rule_id) if rule_id else None
    target=money(q)
    if rule and rule.min_price is not None: target=max(target,money(rule.min_price))
    if rule and rule.max_price is not None: target=min(target,money(rule.max_price))
    decision=MarketplacePriceDecision(seller_tenant_id=seller_tenant_id,listing_id=listing_id,source='competitive',previous_price=money(listing.unit_price),proposed_price=target,floor_price=money(rule.min_price) if rule and rule.min_price is not None else None,ceiling_price=money(rule.max_price) if rule and rule.max_price is not None else None,rule_id=rule.id if rule else None,reason='latest observed competitive price with guardrails',status='accepted')
    self.db.add(decision); listing.unit_price=target; listing.updated_at=datetime.now(timezone.utc); self.db.commit(); self.db.refresh(decision)
    return {'listing_id':listing_id,'price':str(target),'decision_id':decision.id,'competitor_price':str(q)}

def _enforce_health(self,seller_tenant_id,period_start,period_end,reason='automated account health'):
    snap=self.health_snapshot(seller_tenant_id,period_start,period_end)
    if snap.status=='critical':
        x=MarketplaceSellerEnforcement(seller_tenant_id=seller_tenant_id,reason_code='ACCOUNT_HEALTH_CRITICAL',severity='critical',action='restrict_listing',evidence_json={'snapshot_id':snap.id,'defect_rate':str(snap.defect_rate)})
        self.db.add(x); self.db.commit(); self.db.refresh(x); return {'snapshot_id':snap.id,'enforcement_id':x.id,'status':'restricted'}
    return {'snapshot_id':snap.id,'status':snap.status}

def _submit_appeal(self,seller_tenant_id,enforcement_id,reason,evidence=None):
    e=self.db.scalar(select(MarketplaceSellerEnforcement).where(MarketplaceSellerEnforcement.id==enforcement_id,MarketplaceSellerEnforcement.seller_tenant_id==seller_tenant_id))
    if not e: raise MarketplaceCompletionError('enforcement not found')
    x=MarketplaceSellerAppeal(enforcement_id=enforcement_id,seller_tenant_id=seller_tenant_id,reason=reason,evidence_json=evidence or {}); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

def _resolve_appeal(self,seller_tenant_id,appeal_id,approved,notes=''):
    x=self.db.scalar(select(MarketplaceSellerAppeal).where(MarketplaceSellerAppeal.id==appeal_id,MarketplaceSellerAppeal.seller_tenant_id==seller_tenant_id).with_for_update())
    if not x: raise MarketplaceCompletionError('appeal not found')
    e=self.db.get(MarketplaceSellerEnforcement,x.enforcement_id); x.status='approved' if approved else 'rejected'; x.resolution_json={'notes':notes}; x.resolved_at=datetime.now(timezone.utc)
    if approved: e.status='lifted'; e.ends_at=datetime.now(timezone.utc)
    self.db.commit(); return x

def _open_case_sla(self,case_id,due_at,assigned_to=None):
    case=self.db.get(MarketplaceCustomerCase,case_id)
    if not case: raise MarketplaceCompletionError('case not found')
    x=MarketplaceCaseSLA(case_id=case_id,due_at=due_at,assigned_to=assigned_to); self.db.add(x); self.db.add(MarketplaceCaseEvent(case_id=case_id,event_type='sla_opened',payload_json={'due_at':due_at.isoformat()})); self.db.commit(); self.db.refresh(x); return x

def _escalate_case(self,case_id,reason='sla_breach'):
    sla=self.db.scalar(select(MarketplaceCaseSLA).where(MarketplaceCaseSLA.case_id==case_id).with_for_update())
    if not sla: raise MarketplaceCompletionError('case SLA not found')
    sla.escalation_level+=1; sla.status='breached'; self.db.add(MarketplaceCaseEvent(case_id=case_id,event_type='escalated',payload_json={'reason':reason,'level':sla.escalation_level})); self.db.commit(); return sla

def _ship(self,seller_tenant_id,order_id,carrier_code,tracking_number,promised_at=None,service_level='standard'):
    order=self.db.scalar(select(MarketplaceOrder).where(MarketplaceOrder.id==order_id,MarketplaceOrder.seller_tenant_id==seller_tenant_id))
    if not order: raise MarketplaceCompletionError('order not found for seller')
    x=MarketplaceShipment(seller_tenant_id=seller_tenant_id,order_id=order_id,carrier_code=carrier_code,tracking_number=tracking_number,service_level=service_level,promised_at=promised_at); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

def _shipment_event(self,seller_tenant_id,shipment_id,event_code,event_at,location=None,raw=None):
    x=self.db.scalar(select(MarketplaceShipment).join(MarketplaceOrder,MarketplaceOrder.id==MarketplaceShipment.order_id).where(MarketplaceShipment.id==shipment_id,MarketplaceShipment.seller_tenant_id==seller_tenant_id))
    if not x: raise MarketplaceCompletionError('shipment not found')
    ev=MarketplaceShipmentEvent(shipment_id=shipment_id,event_code=event_code,event_at=event_at,location_json=location or {},raw_payload_json=raw or {}); x.status=event_code; self.db.add(ev); self.db.commit(); self.db.refresh(ev); return ev

def _ad_eligible(self,seller_tenant_id,campaign_id,listing_id):
    c=self.db.scalar(select(MarketplaceAdCampaign).where(MarketplaceAdCampaign.id==campaign_id,MarketplaceAdCampaign.seller_tenant_id==seller_tenant_id))
    l=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id,MarketplaceListing.seller_tenant_id==seller_tenant_id))
    if not c or not l: raise MarketplaceCompletionError('campaign/listing not found')
    if l.status!='published' or l.moderation_status!='approved': return False
    return True

def _ad_pacing(self,seller_tenant_id,campaign_id,day_key):
    c=self.db.scalar(select(MarketplaceAdCampaign).where(MarketplaceAdCampaign.id==campaign_id,MarketplaceAdCampaign.seller_tenant_id==seller_tenant_id))
    if not c: raise MarketplaceCompletionError('campaign not found')
    p=self.db.scalar(select(MarketplaceAdPacing).where(MarketplaceAdPacing.campaign_id==campaign_id,MarketplaceAdPacing.day_key==day_key).with_for_update())
    if not p: p=MarketplaceAdPacing(campaign_id=campaign_id,day_key=day_key); self.db.add(p); self.db.flush()
    return p

def _run_report(self,tenant_id,report_job_id,output):
    job=self.db.scalar(select(MarketplaceReportJob).where(MarketplaceReportJob.id==report_job_id,MarketplaceReportJob.tenant_id==tenant_id).with_for_update())
    if not job: raise MarketplaceCompletionError('report job not found')
    run=MarketplaceReportRun(report_job_id=job.id,status='running',attempt=1,started_at=datetime.now(timezone.utc)); self.db.add(run); self.db.flush(); run.status='completed'; run.output_json=output; run.completed_at=datetime.now(timezone.utc); job.status='completed'; job.result_uri=f'memory://report/{run.id}'; job.completed_at=run.completed_at; self.db.commit(); return run

def _deliver_notification(self,tenant_id,notification_id,channel,success=True,error=None):
    n=self.db.scalar(select(MarketplaceNotification).where(MarketplaceNotification.id==notification_id,MarketplaceNotification.tenant_id==tenant_id))
    if not n: raise MarketplaceCompletionError('notification not found')
    d=MarketplaceNotificationDelivery(notification_id=notification_id,channel=channel,status='delivered' if success else 'failed',attempts=1,last_error=error,delivered_at=datetime.now(timezone.utc) if success else None); n.status='delivered' if success else 'queued'; n.delivered_at=d.delivered_at; self.db.add(d); self.db.commit(); return d

def _issue_credential(self,owner_tenant_id,app_id,subject_user_id,scopes,token_hash,expires_at=None):
    app=self.db.scalar(select(MarketplaceIntegrationApp).where(MarketplaceIntegrationApp.id==app_id,MarketplaceIntegrationApp.owner_tenant_id==owner_tenant_id))
    if not app: raise MarketplaceCompletionError('integration app not found')
    missing=set(scopes)-set(app.scopes_json or [])
    if missing: raise MarketplaceCompletionError(f'unsupported scopes: {sorted(missing)}')
    x=MarketplaceIntegrationCredential(integration_app_id=app_id,subject_user_id=subject_user_id,scopes_json=list(scopes),token_hash=token_hash,expires_at=expires_at); self.db.add(x); self.db.commit(); return x

def _consume_rate(self,app_id,window_key):
    app=self.db.get(MarketplaceIntegrationApp,app_id)
    if not app or app.status!='active': raise MarketplaceCompletionError('integration app unavailable')
    b=self.db.scalar(select(MarketplaceRateLimitBucket).where(MarketplaceRateLimitBucket.integration_app_id==app_id,MarketplaceRateLimitBucket.window_key==window_key).with_for_update())
    if not b: b=MarketplaceRateLimitBucket(integration_app_id=app_id,window_key=window_key,used=0,limit_value=app.rate_limit_per_minute); self.db.add(b); self.db.flush()
    if b.used>=b.limit_value: raise MarketplaceCompletionError('integration rate limit exceeded')
    b.used+=1; self.db.commit(); return b

def _record_analytics_event(self,tenant_id,event_type,value=0,entity_id=None,dimensions=None,occurred_at=None):
    x=MarketplaceAnalyticsEvent(tenant_id=tenant_id,event_type=event_type,value=money(value),entity_id=entity_id,dimensions_json=dimensions or {},occurred_at=occurred_at or datetime.now(timezone.utc)); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

def _b2b_quote(self,seller_tenant_id,buyer_user_id,listing_id,quantity,currency,quoted_unit_price=None,expires_at=None):
    listing=self.db.scalar(select(MarketplaceListing).where(MarketplaceListing.id==listing_id,MarketplaceListing.seller_tenant_id==seller_tenant_id))
    if not listing: raise MarketplaceCompletionError('listing not found')
    x=MarketplaceB2BQuote(seller_tenant_id=seller_tenant_id,buyer_user_id=buyer_user_id,listing_id=listing_id,quantity=quantity,currency=currency,quoted_unit_price=quoted_unit_price,expires_at=expires_at); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

def _reserve_bundle(self,seller_tenant_id,bundle_id,order_id,quantity):
    b=self.db.scalar(select(MarketplaceBundle).where(MarketplaceBundle.id==bundle_id,MarketplaceBundle.seller_tenant_id==seller_tenant_id))
    if not b: raise MarketplaceCompletionError('bundle not found')
    if b.status!='published': raise MarketplaceCompletionError('bundle is not sellable')
    comps=b.components_json or []
    x=MarketplaceBundleReservation(bundle_id=bundle_id,order_id=order_id,quantity=quantity,component_snapshot_json=comps,status='reserved'); self.db.add(x); self.db.commit(); return x

def _schedule_subscription(self,seller_tenant_id,offer_id,buyer_user_id,next_run_at):
    offer=self.db.scalar(select(MarketplaceSubscriptionOffer).where(MarketplaceSubscriptionOffer.id==offer_id,MarketplaceSubscriptionOffer.seller_tenant_id==seller_tenant_id,MarketplaceSubscriptionOffer.active.is_(True)))
    if not offer: raise MarketplaceCompletionError('subscription offer unavailable')
    x=MarketplaceSubscriptionInstance(offer_id=offer_id,buyer_user_id=buyer_user_id,next_run_at=next_run_at); self.db.add(x); self.db.commit(); self.db.refresh(x); return x

def _publish_brand(self,owner_tenant_id,store_id):
    store=self.db.scalar(select(MarketplaceBrandStore).join(MarketplaceBrand,MarketplaceBrand.id==MarketplaceBrandStore.brand_id).where(MarketplaceBrandStore.id==store_id,MarketplaceBrand.owner_tenant_id==owner_tenant_id))
    if not store: raise MarketplaceCompletionError('brand store not found')
    brand=self.db.get(MarketplaceBrand,store.brand_id)
    if brand.status!='verified': raise MarketplaceCompletionError('brand must be verified before publication')
    review=MarketplaceBrandContentReview(brand_store_id=store.id,reviewer_tenant_id=owner_tenant_id,status='approved'); self.db.add(review); store.status='published'; store.published_at=datetime.now(timezone.utc); self.db.commit(); return store

def _bulk_validate(self,tenant_id,feed_job_id,rows):
    job=self.db.scalar(select(MarketplaceFeedJob).where(MarketplaceFeedJob.id==feed_job_id,MarketplaceFeedJob.tenant_id==tenant_id))
    if not job: raise MarketplaceCompletionError('feed job not found')
    issues=[]
    for row in rows:
        for field in row.get('required_missing',[]):
            issues.append(MarketplaceBulkIssue(feed_job_id=feed_job_id,row_number=int(row.get('row_number',0)),field_name=field,code='REQUIRED',message=f'{field} is required'))
    self.db.add_all(issues); self.db.commit(); return issues

def _record_search(self,buyer_user_id,query,result_count,clicked_listing_id=None):
    x=MarketplaceSearchEvent(buyer_user_id=buyer_user_id,query=query,result_count=result_count,clicked_listing_id=clicked_listing_id); self.db.add(x); self.db.commit(); return x

MarketplaceCompletionService.preview_checkout_promotions=_promo_checkout
MarketplaceCompletionService.record_price_competitor=_record_price_competitor
MarketplaceCompletionService.reprice_against_market=_reprice_against_market
MarketplaceCompletionService.enforce_health=_enforce_health
MarketplaceCompletionService.submit_appeal=_submit_appeal
MarketplaceCompletionService.resolve_appeal=_resolve_appeal
MarketplaceCompletionService.open_case_sla=_open_case_sla
MarketplaceCompletionService.escalate_case=_escalate_case
MarketplaceCompletionService.create_shipment=_ship
MarketplaceCompletionService.record_shipment_event=_shipment_event
MarketplaceCompletionService.ad_eligible=_ad_eligible
MarketplaceCompletionService.ad_pacing=_ad_pacing
MarketplaceCompletionService.run_report=_run_report
MarketplaceCompletionService.deliver_notification=_deliver_notification
MarketplaceCompletionService.issue_integration_credential=_issue_credential
MarketplaceCompletionService.consume_rate_limit=_consume_rate
MarketplaceCompletionService.record_analytics_event=_record_analytics_event
MarketplaceCompletionService.request_b2b_quote=_b2b_quote
MarketplaceCompletionService.reserve_bundle=_reserve_bundle
MarketplaceCompletionService.schedule_subscription=_schedule_subscription
MarketplaceCompletionService.publish_brand_store=_publish_brand
MarketplaceCompletionService.validate_bulk_rows=_bulk_validate
MarketplaceCompletionService.record_search_event=_record_search
from app.core.models.platform_completion import MarketplacePriceDecision, MarketplaceFeedJob
from app.core.models.marketplace_growth import MarketplaceBundle, MarketplaceSubscriptionOffer, MarketplaceBrand, MarketplaceBrandStore, MarketplaceCustomerCase, MarketplaceReportJob, MarketplaceNotification, MarketplaceIntegrationApp

def _allocate_coupon_budget(self,coupon_id,budget_amount,currency):
    b=self.db.scalar(select(MarketplaceCouponBudget).where(MarketplaceCouponBudget.coupon_id==coupon_id).with_for_update())
    if b:
        b.budget_amount=money(budget_amount); b.currency=currency
    else:
        b=MarketplaceCouponBudget(coupon_id=coupon_id,budget_amount=money(budget_amount),currency=currency); self.db.add(b)
    self.db.commit(); self.db.refresh(b); return b

def _consume_coupon_budget(self,coupon_id,amount):
    b=self.db.scalar(select(MarketplaceCouponBudget).where(MarketplaceCouponBudget.coupon_id==coupon_id).with_for_update())
    if not b: return None
    amount=money(amount)
    if money(b.consumed_amount)+amount>money(b.budget_amount): raise MarketplaceCompletionError('coupon budget exhausted')
    b.consumed_amount=money(b.consumed_amount)+amount; self.db.commit(); return b
MarketplaceCompletionService.allocate_coupon_budget=_allocate_coupon_budget
MarketplaceCompletionService.consume_coupon_budget=_consume_coupon_budget
