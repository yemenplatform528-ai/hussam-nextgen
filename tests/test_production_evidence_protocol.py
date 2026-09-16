import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "production_evidence_protocol.py"


def run_protocol(evidence: Path, output: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--evidence-dir", str(evidence), "--output", str(output)],
        text=True,
        capture_output=True,
        check=True,
    )


def test_empty_evidence_is_fail_closed(tmp_path):
    output = tmp_path / "manifest.json"
    result = run_protocol(tmp_path / "evidence", output)
    assert "closed=0" in result.stdout
    assert "pending_external=10" in result.stdout


def test_valid_envelope_closes_only_matching_gate(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    artifact = evidence / "payments.report.txt"
    artifact.write_text("provider sandbox transaction PASS\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (evidence / "payments.json").write_text(
        json.dumps({
            "gate": "payments",
            "environment": "provider-sandbox",
            "source": "payment-provider-certification",
            "performed_at": "2026-09-13T00:00:00Z",
            "result": "PASS",
            "reviewed_by": "certification-owner",
            "checks": ["capture", "webhook-signature", "refund", "reconciliation"],
            "artifact": {"path": artifact.name, "sha256": digest},
        }),
        encoding="utf-8",
    )
    output = tmp_path / "manifest.json"
    run_protocol(evidence, output)
    payload = json.loads(output.read_text())
    assert payload["closed"] == 1
    assert payload["pending_external"] == 9
    assert next(x for x in payload["gates"] if x["gate"] == "Payments")["state"] == "CLOSED"


def test_hash_mismatch_does_not_close(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    artifact = evidence / "security.report.txt"
    artifact.write_text("security PASS\n", encoding="utf-8")
    (evidence / "security.json").write_text(
        json.dumps({
            "gate": "security", "environment": "ci", "source": "scanner",
            "performed_at": "2026-09-13T00:00:00Z", "result": "PASS", "reviewed_by": "security-owner",
            "checks": ["dependency-scan"], "artifact": {"path": artifact.name, "sha256": "0" * 64},
        }), encoding="utf-8")
    output = tmp_path / "manifest.json"
    run_protocol(evidence, output)
    payload = json.loads(output.read_text())
    assert payload["closed"] == 0
