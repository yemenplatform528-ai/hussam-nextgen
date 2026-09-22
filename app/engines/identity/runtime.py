from sqlalchemy import select
from app.core.models.core import TenantMembership, User, Tenant
from app.core.models.governance import MembershipRole, Role
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
    role_codes = list(session.scalars(
        select(Role.code)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .where(MembershipRole.membership_id == membership.id)
        .order_by(Role.code)
    ))
    # Keep legacy role-based API guards working while deriving authority from
    # the live membership rather than from the JWT. Prefer the most privileged
    # known platform/seller role when a membership has multiple roles.
    role = next((code for code in role_codes if code == "platform_admin"), None)
    role = role or next((code for code in role_codes if code in {"owner", "admin"}), None)
    role = role or (role_codes[0] if role_codes else (membership.role or "member"))
    return RequestContext(user_id=str(user_id), tenant_id=tenant_id,
                          membership_id=membership.id, role=role)
