"""Deterministic business intelligence and bounded agent planning.

AI may analyze facts and propose actions, but execution remains behind the Core command boundary.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.models.ai_intelligence import AIInsight, AIMemory, AIEvaluation
from app.core.models.inventory import InventoryItem, InventoryMovementRecord, InventoryReservation
from app.core.models.commerce import SalesOrder
from app.core.models.procurement import PurchaseOrder
from app.core.models.payments import PaymentIntent, PaymentReconciliation
from app.core.models.logistics import Shipment
from app.core.models.marketplace import MarketplaceSellerProfile, MarketplaceListing, MarketplaceOrder, MarketplacePayout
from app.core.models.governance import OutboxEvent


def _event(db, tenant_id, typ, aggregate_id, payload):
    db.add(OutboxEvent(event_id=str(uuid4()), tenant_id=tenant_id, event_type=typ,
                       aggregate_type='ai', aggregate_id=str(aggregate_id), payload=payload, published=False))


def _now():
    return datetime.now(timezone.utc)


def business_snapshot(db: Session, tenant_id: int) -> dict:
    """Return a tenant-scoped, deterministic operational snapshot."""
    cutoff = _now() - timedelta(days=30)
    sales_total = db.scalar(select(func.coalesce(func.sum(SalesOrder.total), 0)).where(
        SalesOrder.tenant_id == tenant_id, SalesOrder.status != 'cancelled', SalesOrder.created_at >= cutoff)) or 0
    sales_orders = db.scalar(select(func.count()).select_from(SalesOrder).where(
        SalesOrder.tenant_id == tenant_id, SalesOrder.status != 'cancelled', SalesOrder.created_at >= cutoff)) or 0
    purchase_orders = db.scalar(select(func.count()).select_from(PurchaseOrder).where(
        PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.created_at >= cutoff)) or 0
    payments_pending = db.scalar(select(func.count()).select_from(PaymentIntent).where(
        PaymentIntent.tenant_id == tenant_id, PaymentIntent.status.in_(['pending','processing','authorized']))) or 0
    payment_mismatches = db.scalar(select(func.count()).select_from(PaymentReconciliation).where(
        PaymentReconciliation.tenant_id == tenant_id,
        PaymentReconciliation.status.in_(['amount_mismatch','currency_mismatch','unknown']))) or 0
    shipments_open = db.scalar(select(func.count()).select_from(Shipment).where(
        Shipment.tenant_id == tenant_id,
        Shipment.status.in_(['ready','picked_up','in_transit','out_for_delivery','failed']))) or 0
    marketplace_listings = db.scalar(select(func.count()).select_from(MarketplaceListing).where(MarketplaceListing.seller_tenant_id==tenant_id, MarketplaceListing.status=='published', MarketplaceListing.moderation_status=='approved')) or 0
    marketplace_orders = db.scalar(select(func.count()).select_from(MarketplaceOrder).where(MarketplaceOrder.seller_tenant_id==tenant_id, MarketplaceOrder.status!='cancelled', MarketplaceOrder.created_at>=cutoff)) or 0
    marketplace_payouts = db.scalar(select(func.coalesce(func.sum(MarketplacePayout.net_amount),0)).where(MarketplacePayout.seller_tenant_id==tenant_id, MarketplacePayout.status=='eligible')) or 0
    reservations = db.scalar(select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
        InventoryReservation.tenant_id == tenant_id, InventoryReservation.status == 'active')) or 0
    movements_out = db.scalar(select(func.coalesce(func.sum(InventoryMovementRecord.quantity), 0)).where(
        InventoryMovementRecord.tenant_id == tenant_id, InventoryMovementRecord.direction == 'out',
        InventoryMovementRecord.created_at >= cutoff)) or 0
    movements_in = db.scalar(select(func.coalesce(func.sum(InventoryMovementRecord.quantity), 0)).where(
        InventoryMovementRecord.tenant_id == tenant_id, InventoryMovementRecord.direction == 'in',
        InventoryMovementRecord.created_at >= cutoff)) or 0
    return {
        'window_days': 30,
        'sales': {'orders': int(sales_orders), 'total': str(Decimal(str(sales_total)))},
        'purchasing': {'orders': int(purchase_orders)},
        'payments': {'pending': int(payments_pending), 'reconciliation_exceptions': int(payment_mismatches)},
        'logistics': {'open_shipments': int(shipments_open)},
        'marketplace': {'published_listings': int(marketplace_listings), 'orders_30d': int(marketplace_orders), 'eligible_payout_amount': str(Decimal(str(marketplace_payouts)))},
        'inventory': {'active_reservations': str(Decimal(str(reservations))),
                      'in_quantity_30d': str(Decimal(str(movements_in))),
                      'out_quantity_30d': str(Decimal(str(movements_out)))},
    }


def generate_insights(db: Session, tenant_id: int, actor_id: str) -> list[AIInsight]:
    snap = business_snapshot(db, tenant_id)
    findings = []
    if snap['payments']['reconciliation_exceptions']:
        findings.append(('payment_reconciliation', 'high', 'هناك عمليات دفع تحتاج إلى تسوية أو مراجعة.',
                         {'count': snap['payments']['reconciliation_exceptions']}))
    if snap['logistics']['open_shipments']:
        findings.append(('logistics_backlog', 'medium', 'هناك شحنات ما زالت مفتوحة وتحتاج متابعة تشغيلية.',
                         {'count': snap['logistics']['open_shipments']}))
    if snap['payments']['pending']:
        findings.append(('payment_pending', 'medium', 'توجد عمليات دفع معلقة يمكن متابعتها.',
                         {'count': snap['payments']['pending']}))
    if Decimal(snap['inventory']['out_quantity_30d']) > Decimal(snap['inventory']['in_quantity_30d']) and Decimal(snap['inventory']['out_quantity_30d']) > 0:
        findings.append(('inventory_flow', 'medium', 'حركة الخروج خلال آخر 30 يومًا أعلى من حركة الدخول؛ راجع إعادة التوريد.', snap['inventory']))
    if not findings:
        findings.append(('healthy_snapshot', 'info', 'لم تظهر مؤشرات تشغيلية حرجة ضمن البيانات المتاحة.', snap))
    rows=[]
    for kind, severity, title, evidence in findings:
        x=AIInsight(id=str(uuid4()), tenant_id=tenant_id, actor_id=actor_id, kind=kind,
                    severity=severity, title=title, evidence=evidence, status='open')
        db.add(x); rows.append(x)
        _event(db, tenant_id, 'ai.insight.created', x.id, {'kind': kind, 'severity': severity})
    db.commit()
    return rows


def save_memory(db: Session, tenant_id: int, actor_id: str, key: str, value: dict, source: str = 'user'):
    existing = db.scalar(select(AIMemory).where(AIMemory.tenant_id == tenant_id, AIMemory.key == key))
    if existing:
        existing.value = value; existing.source = source; existing.updated_at = _now(); existing.actor_id = actor_id
        x=existing
    else:
        x=AIMemory(id=str(uuid4()), tenant_id=tenant_id, actor_id=actor_id, key=key, value=value, source=source)
        db.add(x)
    _event(db, tenant_id, 'ai.memory.updated', x.id, {'key': key, 'source': source})
    db.commit(); return x


def list_memories(db: Session, tenant_id: int, limit: int = 100):
    return db.scalars(select(AIMemory).where(AIMemory.tenant_id == tenant_id).order_by(AIMemory.updated_at.desc()).limit(min(limit,100))).all()


def plan_agent(db: Session, tenant_id: int, actor_id: str, goal: str) -> dict:
    """Produce a bounded plan using deterministic platform facts; no mutation is executed."""
    snap=business_snapshot(db, tenant_id)
    steps=[{'step':1,'type':'read','tool':'platform.business_snapshot','reason':'جمع الحقائق التشغيلية الحالية'},
           {'step':2,'type':'analyze','tool':'ai.business_insights','reason':'تحليل المؤشرات والمخاطر'}]
    if snap['payments']['reconciliation_exceptions']:
        steps.append({'step':3,'type':'propose','command':'payments.reconciliation.review','requires_approval':True,'reason':'مراجعة استثناءات التسوية'})
    if snap['logistics']['open_shipments']:
        steps.append({'step':len(steps)+1,'type':'propose','command':'logistics.follow_up','requires_approval':True,'reason':'متابعة الشحنات المفتوحة'})
    if not any(s.get('type')=='propose' for s in steps):
        steps.append({'step':len(steps)+1,'type':'report','reason':'لا توجد عملية تغيير مطلوبة بناءً على الحقائق الحالية'})
    return {'goal': goal, 'tenant_id': tenant_id, 'generated_at': _now().isoformat(), 'facts': snap, 'steps': steps,
            'execution_policy':'proposals_only; Core authorization required for every mutation'}


def record_evaluation(db: Session, tenant_id:int, actor_id:str, run_id:str, metric:str, score:Decimal, details:dict):
    if score < 0 or score > 1: raise ValueError('evaluation score must be between 0 and 1')
    x=AIEvaluation(id=str(uuid4()),tenant_id=tenant_id,actor_id=actor_id,run_id=run_id,metric=metric,score=score,details=details)
    db.add(x); _event(db,tenant_id,'ai.evaluation.recorded',x.id,{'run_id':run_id,'metric':metric}); db.commit(); return x
