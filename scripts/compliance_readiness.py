#!/usr/bin/env python3
"""Validate the legal/compliance engineering policy pack without claiming legal approval."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.compliance import ComplianceStatus, PolicyDocument, readiness_summary

POLICY_DIR = ROOT / "docs" / "policies"

POLICY_TITLES = {
    "terms_of_service": "Terms of Service",
    "privacy_notice": "Privacy Notice",
    "seller_terms": "Seller Terms",
    "marketplace_prohibited_goods": "Marketplace Prohibited Goods Policy",
    "returns_refunds_disputes": "Returns, Refunds and Disputes Policy",
    "payments_cod_disclosures": "Payments and COD Disclosures",
    "ip_notice_and_takedown": "Intellectual Property Notice and Takedown",
    "data_retention_schedule": "Data Retention Schedule",
}


def load_policies() -> list[PolicyDocument]:
    policies = []
    for code, title in POLICY_TITLES.items():
        path = POLICY_DIR / f"{code}.md"
        if not path.is_file():
            raise RuntimeError(f"missing policy template: {path}")
        text = path.read_text(encoding="utf-8")
        if "EXTERNAL LEGAL APPROVAL REQUIRED" not in text:
            raise RuntimeError(f"policy is missing explicit external approval boundary: {path}")
        policies.append(PolicyDocument(code, title, "template-v1", ComplianceStatus.READY_FOR_REVIEW, "legal_compliance_owner"))
    return policies


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = readiness_summary(load_policies())
    summary["result"] = "PASS"
    summary["engineering_only"] = True
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print("COMPLIANCE_READINESS_OK")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
