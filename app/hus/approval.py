"""Authoritative approval adapter for the governed HUS runtime.

AIAction approval is accepted only when the approval record is tenant-bound,
approved, explicitly attributed, and the approver still has an active owner/admin
membership. The caller-supplied approval_ref is treated only as an identifier;
it is never trusted by itself.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models.ai_hus import AIAction, AIRun
from app.core.models.core import TenantMembership
from app.core.models.oidc import OIDCIdentity
from app.hus.runtime import RuntimeContext


def verify_ai_action_approval(db: Session, ctx: RuntimeContext) -> bool:
    if not ctx.approval_ref:
        return False

    action = db.scalar(
        select(AIAction).where(
            AIAction.id == ctx.approval_ref,
            AIAction.tenant_id == ctx.tenant_id,
            AIAction.tool_code == ctx.action,
            AIAction.status == "approved",
            AIAction.risk == "mutation",
        )
    )
    if not action or not action.approved_by or not action.approval_provenance:
        return False
    run = db.scalar(select(AIRun).where(
        AIRun.id == action.run_id,
        AIRun.tenant_id == ctx.tenant_id,
    ))
    if run is None or run.actor_id != ctx.actor_id:
        return False
    provenance = action.approval_provenance
    if provenance.get("auth_source") != "oidc":
        return False
    if not provenance.get("oidc_subject") or not provenance.get("oidc_issuer"):
        return False
    identity = db.scalar(select(OIDCIdentity).where(
        OIDCIdentity.user_id == action.approved_by,
        OIDCIdentity.issuer == provenance["oidc_issuer"],
        OIDCIdentity.subject == provenance["oidc_subject"],
    ))
    if identity is None:
        return False
    if ctx.arguments_hash:
        from app.hus.runtime import _hash
        if _hash(action.arguments) != ctx.arguments_hash:
            return False

    membership = db.scalar(
        select(TenantMembership).where(
            TenantMembership.user_id == action.approved_by,
            TenantMembership.tenant_id == ctx.tenant_id,
            TenantMembership.active.is_(True),
            TenantMembership.role.in_({"owner", "admin"}),
        )
    )
    return membership is not None
