from dataclasses import dataclass
from app.core.security.jwt import TokenClaims

class TenantAccessDenied(PermissionError):
    pass

@dataclass(frozen=True)
class RequestContext:
    user_id: str
    tenant_id: int
    membership_id: int
    role: str = "member"
    auth_source: str | None = None
    oidc_subject: str | None = None
    oidc_issuer: str | None = None

def build_context(claims: TokenClaims, *, requested_tenant_id: int | None = None) -> RequestContext:
    if requested_tenant_id is not None and requested_tenant_id != claims.tenant_id:
        raise TenantAccessDenied("requested tenant does not match authenticated tenant")
    return RequestContext(user_id=claims.sub, tenant_id=claims.tenant_id, membership_id=0, role="member", auth_source=claims.auth_source, oidc_subject=claims.oidc_subject, oidc_issuer=claims.oidc_issuer)
