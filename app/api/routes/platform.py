from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_context, get_session
from app.core.services.market_context import MarketContextService

router = APIRouter(prefix="/platform", tags=["platform"])


def _public_runtime_context(runtime: dict) -> dict:
    """Project runtime state into a stable client-safe contract.

    Raw control-plane configuration and provider/internal metadata are never
    exposed to clients. Only explicitly allow-listed behavior is projected.
    """
    market = runtime["market"]
    money = runtime["money"]
    delivery_config = runtime["delivery"].get("configuration", {})
    connectivity_config = runtime["connectivity"].get("configuration", {})
    documents_config = runtime["documents"].get("configuration", {})
    notifications_config = runtime["notifications"].get("configuration", {})
    ai_config = runtime["ai_hus"].get("configuration", {})

    return {
        "schema_version": "1.0",
        "market": {
            "code": market["code"],
            "country_code": market["country_code"],
            "name": market["name"],
            "locale": market["locale"],
            "timezone": market["timezone"],
            "default_currency": market["default_currency"],
            "status": market["status"],
        },
        "money": {
            "currencies": money["currencies"],
            "money_units": [
                {
                    "code": unit["code"],
                    "currency": unit["currency"],
                    "variant": unit["variant"],
                    "name": unit["name"],
                    "name_ar": unit["name_ar"],
                }
                for unit in money["money_units"]
            ],
        },
        "payments": {
            "methods": [
                {
                    "code": method["code"],
                    "name": method["name"],
                    "method_type": method["method_type"],
                    "requires_provider": method["requires_provider"],
                }
                for method in runtime["payments"]["methods"]
            ],
        },
        "geography": runtime["geography"],
        "delivery": {
            "modes": delivery_config.get("modes", []),
        },
        "connectivity": {
            "offline_drafts": bool(connectivity_config.get("offline_drafts", False)),
            "idempotent_mutations": bool(connectivity_config.get("idempotent_mutations", False)),
            "explicit_pending_states": bool(connectivity_config.get("explicit_pending_states", False)),
        },
        "documents": {
            "lifecycle": runtime["documents"].get("lifecycle", []),
            "versioned": bool(runtime["documents"].get("versioned", False)),
            "immutable_versions": bool(runtime["documents"].get("immutable_versions", False)),
            "arabic_first": bool(documents_config.get("arabic_first", False)),
            "templates": documents_config.get("templates", []),
        },
        "notifications": {
            "channels": notifications_config.get("channels", ["in_app"]),
            "tenant_scoped": True,
        },
        "ai_hus": {
            "market_context": runtime["ai_hus"]["market_context"],
            "governance": runtime["ai_hus"]["governance"],
            "arabic_terminology": bool(ai_config.get("arabic_terminology", False)),
            "local_market_context": bool(ai_config.get("local_market_context", False)),
        },
        "capabilities": [
            {
                "code": item["code"],
                "category": item["category"],
                "status": item["status"],
            }
            for item in runtime["capabilities"]
            if item["status"] == "active"
        ],
    }


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
    return _public_runtime_context(service.runtime_context(market))
