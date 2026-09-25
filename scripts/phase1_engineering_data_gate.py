#!/usr/bin/env python3
"""Fail-closed Phase 1 engineering/data admission audit.

This gate does not certify external production systems or invent Yemen data.
It proves that the repository has the required Phase 1 control surfaces and
that unresolved external data remains explicitly fail-closed.
"""
from __future__ import annotations

from pathlib import Path
import ast
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "app",
    "alembic",
    "tests",
    "docs",
    "scripts",
    "Dockerfile",
    "render.yaml",
    "scripts/render_start.sh",
    "requirements.lock",
    "pyproject.toml",
]
REQUIRED_DOCS = [
    "docs/YEMEN_GEOGRAPHY_ACCEPTANCE_GATE.md",
    "docs/YEMEN_GEOGRAPHY_SOURCE_REVIEW.md",
    "docs/YEMEN_PAYMENT_PROVIDER_PRODUCTION_GATE.md",
    "docs/DEVELOPER_PLATFORM_PRODUCT_CONTRACT_2026-09-24.md",
    "docs/FINAL_RELEASE_LOCK_PROTOCOL_2026-09-24.md",
]
REQUIRED_CODE = [
    "scripts/yemen_geography_import.py",
    "scripts/ci_test_evidence.py",
    "scripts/final_release_gate.py",
]

failures: list[str] = []
warnings: list[str] = []

def require(path: str) -> None:
    if not (ROOT / path).exists():
        failures.append(f"missing required path: {path}")

for path in REQUIRED + REQUIRED_DOCS + REQUIRED_CODE:
    require(path)

# The geography gate must remain fail-closed until a reviewed exact artifact
# and acceptance record exist. This is a safety property, not a data shortcut.
geo = (ROOT / "docs/YEMEN_GEOGRAPHY_ACCEPTANCE_GATE.md")
if geo.exists():
    text = geo.read_text(encoding="utf-8")
    if "**PENDING.**" not in text and "**Status:** PENDING" not in text:
        warnings.append("geography gate status is no longer pending; Phase 2 must independently verify the exact accepted artifact")
    if "--apply" not in text or "SHA-256" not in text:
        failures.append("geography gate does not document exact-hash fail-closed apply controls")

# Developer evidence must bind source hash before publication.
route = ROOT / "app/api/routes/developer_platform.py"
if route.exists():
    text = route.read_text(encoding="utf-8")
    for marker in (
        "test_source_hash",
        "body.source_hash.lower() != v.source_hash",
        "v.test_status != \"passed\"",
        "v.test_evidence_hash",
        "v.test_run_id",
    ):
        if marker not in text:
            failures.append(f"developer evidence binding missing: {marker}")

# Migration graph must have one head. Parse revision/down_revision declarations
# without importing application code or connecting to a database.
versions = ROOT / "alembic/versions"
revisions: dict[str, str | None] = {}
children: set[str] = set()
if versions.exists():
    for file in versions.glob("*.py"):
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except SyntaxError as exc:
            failures.append(f"invalid migration syntax: {file}: {exc}")
            continue
        rev = down = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        value = node.value
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            if target.id == "revision":
                                rev = value.value
                            else:
                                down = value.value
        if rev:
            if rev in revisions:
                failures.append(f"duplicate Alembic revision: {rev}")
            revisions[rev] = down
            if down:
                children.add(down)
heads = sorted(set(revisions) - children)
if len(heads) != 1:
    failures.append(f"Alembic migration graph must have exactly one head; found {len(heads)}: {heads}")

# Do not allow an accidental committed secret-like file in the Phase 1 surface.
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT).as_posix()
    if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
        continue
    if path.name in {".env", ".env.local", ".env.production", ".env.prod"}:
        failures.append(f"prohibited environment file present: {rel}")

result = {
    "phase": "PHASE_1_ENGINEERING_AND_DATA_CLOSURE",
    "status": "PASS" if not failures else "FAIL",
    "failures": failures,
    "warnings": warnings,
    "checks": {
        "required_paths": len(REQUIRED),
        "required_control_documents": len(REQUIRED_DOCS),
        "required_control_scripts": len(REQUIRED_CODE),
        "migration_heads": heads,
        "geography_apply": "fail-closed-until-accepted",
        "developer_evidence": "source-bound",
    },
}
print(json.dumps(result, indent=2, sort_keys=True))
sys.exit(1 if failures else 0)
