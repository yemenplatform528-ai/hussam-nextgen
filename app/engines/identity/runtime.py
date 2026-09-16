from sqlalchemy import select
from app.core.models.core import TenantMembership, User, Tenant
from app.core.security.context import RequestContext, TenantAccessDenied

def resolve_active_context(session, user_id: str, tenant_id: int) -> RequestContext:
    user = session.scalar(select(User).where(User.id == str(user_id), User.active.is_(True)))
    tenant = session.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "active"))
    membership = session.scalar(select(TenantMembership).where(
        TenantMembership.user_id == str(user_id),
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.active.is_(True)))
    if user is None or tenant is None or membership is None:
        raise TenantAccessDenied("active user, tenant, and membership are required")
    return RequestContext(user_id=str(user_id), tenant_id=tenant_id,
                          membership_id=membership.id)
