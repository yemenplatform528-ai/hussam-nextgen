"""AI-02 governed commerce intelligence.

Deterministic, domain-grounded intelligence over Marketplace records. This module
never mutates commerce state; it can create governed proposals only through the
AI runtime approval boundary.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from uuid import uuid4
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import Session
from app.core.models.marketplace import MarketplaceListing, MarketplaceOrder, MarketplaceCustomerOrder
from app.core.models.ai_hus import AIRun, AIAction
from app.core.models.ai_foundation import AIAgentDefinition
from app.ai.context import build_context
from app.ai.contracts import ContextItem, DataClass, ToolContract, ActionClass
from app.ai.runtime import create_run, propose_action
from app.ai.foundation import register_tool_contract


def _now(): return datetime.now(timezone.utc)


def _public_listing(x):
    return {"id": x.id, "title": x.title, "slug": x.slug, "description": x.description,
            "currency": x.currency, "unit_price": str(x.unit_price), "market_id": x.market_id,
            "seller_tenant_id": x.seller_tenant_id, "category_id": x.category_id}


def customer_context(db: Session, tenant_id: int, user_id: str, market_id: int | None = None) -> dict:
    q = select(MarketplaceCustomerOrder).where(MarketplaceCustomerOrder.buyer_user_id == user_id)
    if market_id is not None: q = q.where(MarketplaceCustomerOrder.market_id == market_id)
    orders = db.scalars(q.order_by(desc(MarketplaceCustomerOrder.created_at)).limit(10)).all()
    active = [o for o in orders if o.status not in {"completed", "cancelled", "refunded"}]
    return {"scope": {"tenant_id": tenant_id, "user_id": user_id, "market_id": market_id},
            "authority": "marketplace_customer_orders",
            "orders": [{"id": o.id, "reference": o.reference, "status": o.status, "currency": o.currency,
                        "total": str(o.total), "created_at": o.created_at.isoformat(), "market_id": o.market_id} for o in orders],
            "active_order_count": len(active)}


def customer_recommendations(db: Session, tenant_id: int, user_id: str, query: str | None = None,
                              market_id: int | None = None, limit: int = 10) -> dict:
    # Only public marketplace inventory is eligible; seller/tenant records never leak into ranking context.
    stmt = select(MarketplaceListing).where(MarketplaceListing.status == "published",
        MarketplaceListing.moderation_status == "approved")
    if market_id is not None: stmt = stmt.where(MarketplaceListing.market_id == market_id)
    if query:
        token = f"%{query.strip()}%"
        stmt = stmt.where(or_(MarketplaceListing.title.ilike(token), MarketplaceListing.description.ilike(token)))
    rows = db.scalars(stmt.order_by(MarketplaceListing.updated_at.desc()).limit(min(max(limit, 1), 50))).all()
    context = customer_context(db, tenant_id, user_id, market_id)
    return {"query": query, "market_id": market_id, "items": [_public_listing(x) for x in rows],
            "grounding": {"source": "marketplace_listings", "live_records": True}, "customer_context": context}


def seller_intelligence(db: Session, tenant_id: int, market_id: int | None = None) -> dict:
    listing_q = select(func.count()).select_from(MarketplaceListing).where(MarketplaceListing.seller_tenant_id == tenant_id)
    published_q = listing_q.where(MarketplaceListing.status == "published", MarketplaceListing.moderation_status == "approved")
    if market_id is not None:
        listing_q = listing_q.where(MarketplaceListing.market_id == market_id)
        published_q = published_q.where(MarketplaceListing.market_id == market_id)
    orders_q = select(func.count()).select_from(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id == tenant_id)
    if market_id is not None: orders_q = orders_q.where(MarketplaceOrder.market_id == market_id)
    total = db.scalar(listing_q) or 0
    published = db.scalar(published_q) or 0
    orders_30d = db.scalar(orders_q.where(MarketplaceOrder.created_at >= _now() - timedelta(days=30))) or 0
    paused = db.scalar(select(func.count()).select_from(MarketplaceListing).where(
        MarketplaceListing.seller_tenant_id == tenant_id, MarketplaceListing.status == "paused",
        *( [MarketplaceListing.market_id == market_id] if market_id is not None else []))) or 0
    opportunities = []
    if total and published < total:
        opportunities.append({"kind": "publication_gap", "severity": "medium", "reason": "Some listings are not publicly discoverable."})
    if paused:
        opportunities.append({"kind": "paused_listings", "severity": "medium", "count": paused})
    if orders_30d == 0 and published:
        opportunities.append({"kind": "zero_order_signal", "severity": "low", "reason": "Published listings have no marketplace orders in the last 30 days."})
    return {"seller_tenant_id": tenant_id, "market_id": market_id,
            "listing_count": int(total), "published_approved_count": int(published),
            "orders_30d": int(orders_30d), "opportunities": opportunities,
            "authority": "marketplace domain records"}


def create_commerce_proposal(db: Session, tenant_id: int, actor_id: str, goal: str, *, market_id: int | None = None) -> dict:
    """Create a proposal-only AI run; no marketplace mutation occurs."""
    seller = seller_intelligence(db, tenant_id, market_id)
    payload = {"goal": goal, "market_id": market_id, "seller_intelligence": seller}
    run = create_run(db, tenant_id, actor_id, "marketplace_commerce_intelligence", payload, model=None)
    # The proposal tool is an explicit governed capability. It never performs a
    # Marketplace mutation; its EXECUTE class exists only to force approval.
    from sqlalchemy import select
    from app.core.models.ai_hus import AIToolDefinition
    if not db.scalar(select(AIToolDefinition).where(AIToolDefinition.tenant_id == tenant_id, AIToolDefinition.code == "marketplace.commerce_review")):
        register_tool_contract(db, tenant_id, ToolContract(
            code="marketplace.commerce_review",
            description="Create a governed review proposal for Marketplace operations; no direct domain mutation.",
            action_class=ActionClass.EXECUTE, risk_class="high", data_classes=[DataClass.TENANT],
            requires_approval=True, idempotent=True, input_schema={"type":"object"}),
            handler_key="marketplace.commerce_review")
    action = None
    if seller["opportunities"]:
        action = propose_action(db, tenant_id, actor_id, run.id, "marketplace.commerce_review", {"market_id": market_id, "goal": goal})
    return {"run_id": run.id, "status": run.status, "facts": seller,
            "proposal": None if action is None else {"id": action.id, "status": action.status, "tool_code": action.tool_code,
                                                       "requires_approval": action.status == "pending_approval"},
            "execution": "no mutation performed; domain authority remains unchanged"}


def build_customer_ai_context(db: Session, tenant_id: int, user_id: str, query: str, market_id: int | None = None):
    facts = customer_recommendations(db, tenant_id, user_id, query, market_id)
    return build_context(db, tenant_id, owner_id=user_id, agent_code="customer_commerce_assistant",
        system_policy="Use only grounded marketplace facts. Never infer authority from memory. Never mutate commerce state without governed approval.",
        live_facts=[ContextItem(source="marketplace", kind="customer_commerce", data_class=DataClass.TENANT, trusted=True, content=facts)])
