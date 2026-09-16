"""Production HUS domain bindings.

Only explicit, reviewed application handlers may be bound. HUS never resolves
Python imports, SQL, URLs, shell commands, or model-generated handler names.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Callable
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.ai.tools import execute_read_tool
from app.core.models.payments import PaymentIntent
from app.core.models.governance import OutboxEvent
from app.core.models.commerce import SalesOrder
from app.core.models.inventory import InventoryItem
from app.engines.commerce import CommerceProductionService, OrderLineInput

class HUSBindingError(ValueError):
    pass

Handler = Callable[[Session, object, dict], dict]

READ_TOOL_BINDINGS = {
    "retail.catalog.read": "retail.overview",
    "inventory.inventory.read": "inventory.stock",
    "commerce.sales.read": "sales.summary",
    "marketplace.marketplace.read": "marketplace.overview",
}

def _ai_read(tool_code: str) -> Handler:
    def handler(db: Session, ctx, args: dict) -> dict:
        return execute_read_tool(db, ctx.tenant_id, tool_code, args)
    return handler

def _finance_read(db: Session, ctx, args: dict) -> dict:
    from app.core.models.core import Journal
    count = db.scalar(select(func.count()).select_from(Journal).where(Journal.tenant_id == ctx.tenant_id)) or 0
    return {"journals": int(count)}

def _payments_read(db: Session, ctx, args: dict) -> dict:
    count = db.scalar(select(func.count()).select_from(PaymentIntent).where(PaymentIntent.tenant_id == ctx.tenant_id)) or 0
    return {"payment_intents": int(count)}

def _commerce_create(db: Session, ctx, args: dict) -> dict:
    reference = str(args.get("reference", "")).strip()
    currency = str(args.get("currency", "")).strip()
    lines = args.get("lines")
    if not reference or not currency or not isinstance(lines, list) or not lines:
        raise HUSBindingError("commerce.sales.create requires reference, currency and non-empty lines")
    if len(lines) > 100:
        raise HUSBindingError("commerce.sales.create line limit exceeded")
    parsed = []
    for line in lines:
        if not isinstance(line, dict):
            raise HUSBindingError("each sales line must be an object")
        parsed.append(OrderLineInput(
            item_id=str(line.get("item_id", "")),
            quantity=Decimal(str(line.get("quantity", "0"))),
            unit_price=Decimal(str(line.get("unit_price", "0"))),
        ))
    svc = CommerceProductionService(db)
    order = svc.create_order(ctx.tenant_id, reference, currency, parsed, commit=False)
    return {"order_id": order.id, "reference": order.reference, "status": order.status, "total": str(order.total), "currency": order.currency}

def build_production_bindings() -> dict[str, Handler]:
    bindings = {action: _ai_read(tool) for action, tool in READ_TOOL_BINDINGS.items()}
    bindings["finance.finance.read"] = _finance_read
    bindings["payments.payments.read"] = _payments_read
    bindings["commerce.sales.create"] = _commerce_create
    return bindings

def register_production_bindings(runtime) -> None:
    for action, handler in build_production_bindings().items():
        if action.split('.', 1)[1].endswith('.create') or action.endswith('.create'):
            runtime.register_mutation_handler(action, handler)
        else:
            runtime.register_read_handler(action, handler)
