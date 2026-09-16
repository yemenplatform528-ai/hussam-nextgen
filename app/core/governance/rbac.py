from sqlalchemy import select

from app.core.models.governance import (
    MembershipRole, RolePermission, PermissionRecord
)
from app.core.models.core import TenantMembership
from app.core.governance.policy import PolicyDenied

def permissions_for_membership(session, membership_id: int) -> set[str]:
    membership = session.scalar(
        select(TenantMembership).where(TenantMembership.id == membership_id)
    )
    if membership is None or not membership.active:
        raise PolicyDenied("membership is not active")

    rows = session.execute(
        select(PermissionRecord.code)
        .join(RolePermission, RolePermission.permission_id == PermissionRecord.id)
        .join(MembershipRole, MembershipRole.role_id == RolePermission.role_id)
        .where(MembershipRole.membership_id == membership_id)
    )
    return {code for (code,) in rows}

def require_permission(session, membership_id: int, permission: str) -> None:
    if permission not in permissions_for_membership(session, membership_id):
        raise PolicyDenied(f"permission denied: {permission}")
