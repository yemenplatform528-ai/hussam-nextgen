"""Provider- and jurisdiction-neutral legal/compliance readiness contracts.

These controls make the platform ready to receive approved legal policy artifacts.
They do not determine what the law requires and never represent legal advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable


class ComplianceStatus(str, Enum):
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"


@dataclass(frozen=True)
class PolicyDocument:
    code: str
    title: str
    version: str
    status: ComplianceStatus
    owner_role: str
    public: bool = True
    external_approval_required: bool = True

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9_]+", self.code):
            raise ValueError("policy code must be lowercase snake_case")
        if not self.title.strip() or not self.version.strip() or not self.owner_role.strip():
            raise ValueError("policy title, version and owner_role are required")
        if self.external_approval_required and self.status is ComplianceStatus.APPROVED:
            raise ValueError("approved policy requires external approval evidence")


@dataclass(frozen=True)
class ComplianceControl:
    code: str
    title: str
    required_policy_codes: tuple[str, ...]
    external_evidence_required: bool = True

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.title.strip():
            raise ValueError("compliance control code and title are required")
        if not self.required_policy_codes:
            raise ValueError("each compliance control needs policy references")


REQUIRED_POLICY_CODES = (
    "terms_of_service",
    "privacy_notice",
    "seller_terms",
    "marketplace_prohibited_goods",
    "returns_refunds_disputes",
    "payments_cod_disclosures",
    "ip_notice_and_takedown",
    "data_retention_schedule",
)

REQUIRED_CONTROLS = (
    ComplianceControl("consumer_terms", "Consumer terms and disclosures", ("terms_of_service", "returns_refunds_disputes")),
    ComplianceControl("privacy_and_data", "Privacy and data governance", ("privacy_notice", "data_retention_schedule")),
    ComplianceControl("seller_governance", "Seller marketplace governance", ("seller_terms", "marketplace_prohibited_goods")),
    ComplianceControl("payments_disclosures", "Payment and COD disclosures", ("payments_cod_disclosures",)),
    ComplianceControl("intellectual_property", "Intellectual property notices", ("ip_notice_and_takedown",)),
)


def validate_policy_pack(policies: Iterable[PolicyDocument]) -> tuple[str, ...]:
    items = tuple(policies)
    codes = [p.code for p in items]
    if len(codes) != len(set(codes)):
        raise ValueError("duplicate policy code")
    missing = tuple(code for code in REQUIRED_POLICY_CODES if code not in set(codes))
    if missing:
        raise ValueError("missing required policies: " + ", ".join(missing))
    for control in REQUIRED_CONTROLS:
        for code in control.required_policy_codes:
            if code not in set(codes):
                raise ValueError(f"control {control.code} references missing policy {code}")
    return tuple(p.code for p in items)


def readiness_summary(policies: Iterable[PolicyDocument]) -> dict[str, object]:
    items = tuple(policies)
    validate_policy_pack(items)
    approved = [p.code for p in items if p.status is ComplianceStatus.APPROVED]
    pending = [p.code for p in items if p.status is not ComplianceStatus.APPROVED]
    return {
        "required_policies": len(REQUIRED_POLICY_CODES),
        "present_policies": len(items),
        "approved_policies": len(approved),
        "pending_policies": pending,
        "external_approval_required": True,
        "status": "PENDING_EXTERNAL" if pending else "PENDING_EXTERNAL_LEGAL_REVIEW",
    }
