#!/usr/bin/env python3
"""Fail-closed production evidence registrar.

A gate can only close from an evidence envelope that identifies the gate, the
real environment/source, the performed checks, a review decision, and a
SHA-256 hash of the externally produced artifact. Configuration and arbitrary
files are never sufficient.
"""
from __future__ import annotations

import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path

GATES = {
    "identity_oidc": "Identity/OIDC",
    "postgresql": "PostgreSQL",
    "payments": "Payments",
    "accounting": "Accounting",
    "logistics": "Logistics",
    "browser_mobile_e2e": "Browser/mobile E2E",
    "security": "Security",
    "backup_dr_observability": "Backup/DR/Observability",
    "operations": "Operations",
    "legal_compliance": "Legal/Compliance",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_envelope(root: Path, gate: str, envelope_path: Path) -> tuple[bool, str | None, dict]:
    try:
        data = json.loads(envelope_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"invalid JSON: {exc}", {}
    if data.get("gate") != gate:
        return False, "gate field mismatch", data
    required = ("environment", "source", "performed_at", "result", "reviewed_by", "artifact")
    missing = [k for k in required if not data.get(k)]
    if missing:
        return False, "missing fields: " + ", ".join(missing), data
    if data.get("result") != "PASS":
        return False, "result is not PASS", data
    if not isinstance(data.get("checks"), list) or not data["checks"]:
        return False, "checks must be a non-empty list", data
    artifact = data["artifact"]
    if not isinstance(artifact, dict) or not artifact.get("path") or not HEX64.fullmatch(str(artifact.get("sha256", ""))):
        return False, "artifact.path and a 64-character SHA-256 are required", data
    artifact_path = (envelope_path.parent / artifact["path"]).resolve()
    if root not in artifact_path.parents:
        return False, "artifact escapes evidence directory", data
    if not artifact_path.is_file() or artifact_path.resolve() == envelope_path.resolve():
        return False, "referenced artifact does not exist", data
    actual = sha256(artifact_path)
    if actual != artifact["sha256"]:
        return False, "artifact SHA-256 mismatch", data
    return True, None, data


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    root = args.evidence_dir.resolve()
    rows = []
    for key, name in GATES.items():
        envelope = root / f"{key}.json"
        if envelope.is_file():
            ok, reason, data = validate_envelope(root, key, envelope)
            if ok:
                artifact = data["artifact"]["path"]
                rows.append({"gate": name, "state": "CLOSED", "artifact": artifact, "sha256": data["artifact"]["sha256"], "environment": data["environment"]})
            else:
                rows.append({"gate": name, "state": "PENDING_EXTERNAL", "artifact": None, "sha256": None, "reason": reason})
        else:
            rows.append({"gate": name, "state": "PENDING_EXTERNAL", "artifact": None, "sha256": None, "reason": "evidence envelope missing"})
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "principle": "artifact-backed, reviewed evidence only; configuration is not evidence",
        "closed": sum(r["state"] == "CLOSED" for r in rows),
        "pending_external": sum(r["state"] != "CLOSED" for r in rows),
        "gates": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"closed={payload['closed']}")
    print(f"pending_external={payload['pending_external']}")
    print(f"evidence_manifest={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
