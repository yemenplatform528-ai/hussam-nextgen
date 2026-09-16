#!/usr/bin/env python3
"""Fail-closed audit for external production evidence."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
register = ROOT / "docs" / "PRODUCTION_EVIDENCE_REGISTER.md"
text = register.read_text(encoding="utf-8")
required = [
    "Identity/OIDC", "PostgreSQL", "Payments", "Accounting", "Logistics",
    "Browser/mobile E2E", "Security", "Backup/DR/Observability", "Operations",
    "Legal/Compliance",
]
missing = [name for name in required if name not in text]
if missing:
    raise SystemExit("MISSING_EVIDENCE_REGISTER_ROWS: " + ", ".join(missing))
pending = sum(1 for line in text.splitlines() if "| PENDING_EXTERNAL |" in line)
closed = sum(1 for line in text.splitlines() if "| CLOSED |" in line)
print(f"production_evidence_rows: {len(required)}")
print(f"closed: {closed}")
print(f"pending_external: {pending}")
if closed == len(required):
    print("production_evidence_audit: PASS")
else:
    print("production_evidence_audit: PENDING_EXTERNAL_EVIDENCE")
