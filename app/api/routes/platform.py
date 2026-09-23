from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_context, get_session
from app.core.services.market_context import MarketContextService

router = APIRouter(prefix="/platform", tags=["platform"])

@router.get("/market-context/{market_code}")
def client_market_context(
    market_code: str,
    ctx=Depends(get_context),
    db=Depends(get_session),
):
    """Return the stable, tenant-safe runtime context consumed by clients.

    Control-plane-only metadata and raw capability configuration are intentionally
    excluded. Domain engines remain authoritative for business operations.
    """
    service = MarketContextService(db)
    market = service.get_market(market_code)
    if not market:
        raise HTTPException(status_code=404, detail="market not found")
    if market.status != "active":
        raise HTTPException(status_code=409, detail="market is not active")

    runtime = service.runtime_context(market)
    capability_states = [
        {
            "code": item["code"],
            "category": item["category"],
            "status": item["status"],
        }
        for item in runtime["capabilities"]
        if item["status"] == "active"
    ]

    return {
        "schema_version": "1.0",
        "market": runtime["market"],
        "money": runtime["money"],
        "payments": runtime["payments"],
        "geography": runtime["geography"],
        "delivery": runtime["delivery"],
        "connectivity": runtime["connectivity"],
        "documents": runtime["documents"],
        "notifications": runtime["notifications"],
        "ai_hus": runtime["ai_hus"],
        "capabilities": capability_states,
    }
