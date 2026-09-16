import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.compliance import (
    ComplianceStatus,
    PolicyDocument,
    REQUIRED_POLICY_CODES,
    readiness_summary,
    validate_policy_pack,
)


ROOT = Path(__file__).resolve().parents[1]


def policy(code, status=ComplianceStatus.READY_FOR_REVIEW):
    return PolicyDocument(code, code.replace("_", " "), "v1", status, "legal_compliance_owner")


def test_required_policy_pack_is_complete():
    items = [policy(code) for code in REQUIRED_POLICY_CODES]
    assert validate_policy_pack(items) == tuple(REQUIRED_POLICY_CODES)
    summary = readiness_summary(items)
    assert summary["required_policies"] == 8
    assert summary["approved_policies"] == 0
    assert summary["status"] == "PENDING_EXTERNAL"


def test_missing_policy_is_rejected():
    items = [policy(code) for code in REQUIRED_POLICY_CODES[:-1]]
    with pytest.raises(ValueError, match="missing required policies"):
        validate_policy_pack(items)


def test_duplicate_policy_is_rejected():
    items = [policy(code) for code in REQUIRED_POLICY_CODES] + [policy(REQUIRED_POLICY_CODES[0])]
    with pytest.raises(ValueError, match="duplicate policy"):
        validate_policy_pack(items)


def test_approved_policy_requires_external_boundary():
    with pytest.raises(ValueError, match="external approval evidence"):
        PolicyDocument("privacy_notice", "Privacy", "v1", ComplianceStatus.APPROVED, "legal_compliance_owner")


def test_policy_templates_have_explicit_external_boundary():
    policy_dir = ROOT / "docs" / "policies"
    for code in REQUIRED_POLICY_CODES:
        text = (policy_dir / f"{code}.md").read_text(encoding="utf-8")
        assert "EXTERNAL LEGAL APPROVAL REQUIRED" in text
        assert "NOT LEGAL ADVICE" in text


def test_readiness_script_is_secret_free_and_engineering_only(tmp_path):
    out = tmp_path / "g10.json"
    result = subprocess.run(
        [sys.executable, "scripts/compliance_readiness.py", "--output", str(out)],
        text=True,
        capture_output=True,
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out.read_text())
    assert payload["result"] == "PASS"
    assert payload["engineering_only"] is True
    assert payload["status"] == "PENDING_EXTERNAL"
    assert "COMPLIANCE_READINESS_OK" in result.stdout
    assert "secret" not in out.read_text().lower()
