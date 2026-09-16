"""Single boundary for turning verified JWT claims into an active tenant context."""

from sqlalchemy.orm import Session

from app.core.security.context import RequestContext, TenantAccessDenied
from app.core.security.jwt import TokenClaims
from app.engines.identity.runtime import resolve_active_context


def authenticate_context(
    session: Session,
    claims: TokenClaims,
    *,
    requested_tenant_id: int | None = None,
) -> RequestContext:
    """Resolve an authenticated request to a live user/tenant membership.

    The JWT identifies the requested tenant, but the database remains the
    authority for user status, tenant status, and active membership.
    """
    if requested_tenant_id is not None and requested_tenant_id != claims.tenant_id:
        raise TenantAccessDenied("requested tenant does not match authenticated tenant")
    return resolve_active_context(session, claims.sub, claims.tenant_id)
