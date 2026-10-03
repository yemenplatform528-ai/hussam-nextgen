"""Authoritative approval adapter for the governed HUS runtime.

AIAction approval is accepted only when the approval record is tenant-bound,
approved, explicitly attributed, bound to the exact compiled execution intent,
and the approver still has an active owner/admin membership.
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
    binding = provenance.get("execution_binding") or {}
    if binding.get("compilation_id") != ctx.compilation_id:
        return False
    if binding.get("step_id") != ctx.step_id:
        return False
    if binding.get("plan_hash") != ctx.plan_hash:
        return False
    if binding.get("action") != ctx.action:
        return False
    if binding.get("idempotency_key") != ctx.idempotency_key:
        return False
    if binding.get("arguments_hash") != ctx.arguments_hash:
        return False

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
