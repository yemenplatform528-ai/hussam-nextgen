import os
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from app.core.security.jwt import encode_hs256
from app.core.security.oidc import OIDCError, OIDCSettings, authorization_url, discover, exchange_code, make_state, validate_id_token, verify_state, extract_nonce, normalize_identity

router = APIRouter(prefix="/auth/oidc", tags=["oidc"])


def _secure_cookie(request: Request) -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() in {"production", "staging"} or request.url.scheme == "https"


@router.get("/login")
def login(request: Request):
    try:
        settings = OIDCSettings.from_env()
        metadata = discover(settings)
        state = make_state(settings)
        nonce = extract_nonce(state)
        url = authorization_url(settings, metadata, state, nonce)
    except OIDCError as exc:
        raise HTTPException(status_code=503, detail="OIDC is not configured") from exc
    response = RedirectResponse(url, status_code=302)
    response.set_cookie("hussam_oidc_state", state, max_age=600, httponly=True, secure=_secure_cookie(request), samesite="lax", path="/api/v1/auth/oidc")
    return response


@router.get("/callback")
def callback(request: Request, code: str = Query(""), state: str = Query(""), error: str | None = Query(default=None)):
    if error:
        raise HTTPException(status_code=401, detail="OIDC authentication was denied")
    if not code or not state:
        raise HTTPException(status_code=400, detail="OIDC callback is incomplete")
    cookie_state = request.cookies.get("hussam_oidc_state")
    if not cookie_state or not hmac_compare(cookie_state, state):
        raise HTTPException(status_code=400, detail="invalid OIDC state")
    try:
        settings = OIDCSettings.from_env()
        if not verify_state(settings, state):
            raise OIDCError("expired OIDC state")
        metadata = discover(settings)
        tokens = exchange_code(settings, metadata, code)
        claims = validate_id_token(settings, metadata, tokens["id_token"], nonce=extract_nonce(state))
        subject, email = normalize_identity(claims)
    except OIDCError as exc:
        raise HTTPException(status_code=401, detail="OIDC authentication failed") from exc

    # Do not create or silently elevate a tenant here. Tenant membership remains
    # the platform authorization authority and must be selected/validated before
    # a local API token can be issued.
    from app.core.db.config import DatabaseSettings
    from app.core.db.session import make_engine, make_session_factory
    from app.core.models.core import User, TenantMembership
    from app.core.models.oidc import OIDCIdentity
    from sqlalchemy import select
    settings_db = DatabaseSettings.from_env()
    engine = make_engine(settings_db)
    session = make_session_factory(engine)()
    try:
        identity = session.scalar(select(OIDCIdentity).where(OIDCIdentity.issuer == settings.issuer, OIDCIdentity.subject == subject))
        user = session.scalar(select(User).where(User.id == identity.user_id, User.active.is_(True))) if identity else None
        if user is None:
            raise HTTPException(status_code=403, detail="OIDC identity is not provisioned")
        memberships = session.scalars(select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.active.is_(True))).all()
        if not memberships:
            raise HTTPException(status_code=403, detail="active tenant membership required")
        if len(memberships) != 1:
            raise HTTPException(status_code=409, detail="tenant selection is required for this identity")
        tenant_id = memberships[0].tenant_id
    finally:
        session.close()
        engine.dispose()

    token = encode_hs256({"sub": str(user.id), "tenant_id": int(tenant_id), "exp": int(__import__('time').time()) + 3600, "iss": "hussam-nextgen"}, os.getenv("JWT_SECRET", ""))
    response = RedirectResponse("/console/", status_code=303)
    response.set_cookie("hussam_token", token, max_age=3600, httponly=True, secure=_secure_cookie(request), samesite="lax", path="/")
    response.delete_cookie("hussam_oidc_state", path="/api/v1/auth/oidc")
    return response

@router.post("/logout")
def logout():
    response = RedirectResponse("/console/", status_code=303)
    response.delete_cookie("hussam_token", path="/")
    return response


def hmac_compare(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a, b)
