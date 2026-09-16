from dataclasses import dataclass
from app.core.security.jwt import TokenClaims

class TenantAccessDenied(PermissionError):
    pass

@dataclass(frozen=True)
class RequestContext:
    user_id: str
    tenant_id: int
    membership_id: int

def build_context(claims: TokenClaims, *, requested_tenant_id: int | None = None) -> RequestContext:
    if requested_tenant_id is not None and requested_tenant_id != claims.tenant_id:
        raise TenantAccessDenied("requested tenant does not match authenticated tenant")
    return RequestContext(user_id=claims.sub, tenant_id=claims.tenant_id, membership_id=0)
