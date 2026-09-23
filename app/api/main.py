import os
from uuid import uuid4
from app.core.security.production import ProductionConfigError, ProductionSettings
from app.core.observability import configure_logging, metrics, request_id_ctx
from app.core.rate_limit import RateLimiter, RedisRateLimiter
from app.core.security.proxy import client_ip
from sqlalchemy import create_engine, text
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.domains.registry import DOMAINS
from app.api.routes import ai_foundation, inventory, commerce, procurement, payments, documents, finance, logistics, workflow, session, dashboard, operations, retail, ai_hus, marketplace, marketplace_growth, marketplace_completion, oidc, carriers, ai_commerce, ai_agents, ai_product, developer_platform, platform

VERSION="1.0.0"
configure_logging()
RELEASE_PROFILE="full-development"
_rate_limit_limit = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "600"))
_rate_limit_backend = os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower()
if _rate_limit_backend == "redis" and os.getenv("RATE_LIMIT_REDIS_URL"):
    _rate_limit = RedisRateLimiter(os.environ["RATE_LIMIT_REDIS_URL"], _rate_limit_limit)
else:
    _rate_limit = RateLimiter(_rate_limit_limit)
app=FastAPI(title="Hussam Yemeni Sovereign Platform — NextGen",version=VERSION)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Health/observability probes must remain available during incidents.
    if request.url.path not in {"/health", "/ready", "/metrics"}:
        client_key = client_ip(request)
        allowed, remaining, retry_after = _rate_limit.check(client_key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(_rate_limit.limit), "X-RateLimit-Remaining": "0"},
            )
    else:
        remaining = _rate_limit.limit
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    token = request_id_ctx.set(request_id)
    started = __import__("time").perf_counter()
    failed = False
    try:
        response = await call_next(request)
        failed = response.status_code >= 500
    except Exception:
        failed = True
        raise
    finally:
        metrics.observe_request(__import__("time").perf_counter() - started, failed)
        request_id_ctx.reset(token)
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-RateLimit-Limit", str(_rate_limit.limit))
    response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
    response.headers.setdefault("Cache-Control", "no-store" if request.url.path.startswith("/api/") else "no-cache")
    if os.getenv("ENVIRONMENT", "development").lower() in {"production", "staging"}:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

@app.exception_handler(ValueError)
async def domain_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
app.include_router(inventory.router,prefix="/api/v1")
app.include_router(commerce.router,prefix="/api/v1")
app.include_router(procurement.router,prefix="/api/v1")
app.include_router(payments.router,prefix="/api/v1")
app.include_router(documents.router,prefix="/api/v1")
app.include_router(finance.router,prefix="/api/v1")
app.include_router(logistics.router,prefix="/api/v1")
app.include_router(carriers.router,prefix="/api/v1")
app.include_router(workflow.router,prefix="/api/v1")
app.include_router(session.router,prefix="/api/v1")
app.include_router(dashboard.router,prefix="/api/v1")
app.include_router(operations.router,prefix="/api/v1")
app.include_router(retail.router,prefix="/api/v1")
app.include_router(ai_hus.router,prefix="/api/v1")
app.include_router(ai_foundation.router,prefix="/api/v1")
app.include_router(ai_commerce.router,prefix="/api/v1")
app.include_router(ai_agents.router,prefix="/api/v1")
app.include_router(ai_product.router,prefix="/api/v1")
app.include_router(developer_platform.router,prefix="/api/v1")
app.include_router(platform.router,prefix="/api/v1")
app.include_router(marketplace.router,prefix="/api/v1")
app.include_router(marketplace_growth.router,prefix="/api/v1")
app.include_router(marketplace_completion.router,prefix="/api/v1")
app.include_router(oidc.router,prefix="/api/v1")
app.mount("/console", StaticFiles(directory="app/ui", html=True), name="console")

@app.get("/health")
def health(): return {"status":"ok","platform":"hussam-nextgen","version":VERSION}

@app.get("/ready")
def readiness(deep: bool | None = None):
    try:
        settings = ProductionSettings.from_env(strict=False)
        if not settings.database_url:
            metrics.set_readiness(False)
            return JSONResponse(status_code=503, content={"status":"not_ready","reason":"DATABASE_URL missing"})
        if deep is None:
            deep = settings.environment in {"production", "staging"}
        if deep:
            try:
                engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                engine.dispose()
            except Exception:
                metrics.set_readiness(False)
                return JSONResponse(status_code=503, content={"status":"not_ready","database_configured":True,"database_reachable":False,"environment":settings.environment})
        metrics.set_readiness(True)
        return {"status":"ready","database_configured":True,"database_reachable":bool(deep),"environment":settings.environment}
    except ProductionConfigError as exc:
        metrics.set_readiness(False)
        return JSONResponse(status_code=503, content={"status":"not_ready","reason":str(exc)})

@app.get("/metrics")
def metrics_endpoint():
    return JSONResponse(content=metrics.prometheus(), media_type="text/plain; version=0.0.4")
@app.get("/api/v1/platform/manifest")
def manifest():
    return {"domains":DOMAINS,"status":"api","version":VERSION,"release_profile":RELEASE_PROFILE,"architecture":{"core":"sovereign","engines":["identity","finance","inventory","commerce","payments","logistics"],"verticals":["marketplace"],"products":["marketplace","retail"],"capabilities":["catalog","offers","featured_offer","checkout","payments","fees","settlement","returns","refunds","seller_center","pricing","promotions","brands","advertising","b2b","bundles","subscriptions","customer_service","seller_health","warehouses","inventory_transfer","pickup_points","service_areas","reports","notifications","integrations","ai","hus"]}}

@app.get("/api/v1/platform/release")
def release_profile():
    return {"release":"Hussam NextGen Unified Platform 1.0","profile":RELEASE_PROFILE,"principle":"one unified platform; sovereign core and shared engine authorities","status":"release-candidate"}
