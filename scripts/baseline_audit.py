#!/usr/bin/env python3
"""Static repository baseline checks for Hussam NextGen.

This is intentionally dependency-light so it can run before the full test stack.
It does not claim to replace professional SAST/SCA/secret scanners.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FAILURES: list[str] = []
WARNINGS: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def check_required_files() -> None:
    required = [
        ".gitignore", ".env.example", "README.md", "SECURITY.md",
        "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE", "pyproject.toml",
        "requirements.lock", "alembic.ini", ".github/workflows/ci.yml",
        "docs/REPOSITORY_PRODUCTION_BASELINE.md",
        "docs/PRODUCTION_GATES.md",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            fail(f"missing required repository file: {rel}")


def check_forbidden_files() -> None:
    forbidden = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|.*\.db|.*\.sqlite3?|.*\.log)$", re.I)
    ignored_dirs = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "node_modules"}
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in ignored_dirs for part in p.parts):
            continue
        if forbidden.search(p.relative_to(ROOT).as_posix()) and p.name != ".env.example":
            fail(f"forbidden secret/runtime artifact tracked in release tree: {p.relative_to(ROOT)}")


def check_obvious_secrets() -> None:
    patterns = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9_\-/+=]{24,}[\"']?"),
    ]
    allowed = {".env.example", "docs/REPOSITORY_PRODUCTION_BASELINE.md"}
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in {".git", ".pytest_cache", "__pycache__", ".venv", "venv"} for part in p.parts):
            continue
        if p.name in allowed:
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for pat in patterns:
            if pat.search(text):
                fail(f"possible hard-coded secret pattern in {p.relative_to(ROOT)}")
                break


def check_architecture_boundaries() -> None:
    domain_roots = [ROOT / "app" / "domains"]
    violations: list[str] = []
    for root in domain_roots:
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            try:
                tree = ast.parse(p.read_text())
            except SyntaxError as exc:
                fail(f"syntax error in {p.relative_to(ROOT)}: {exc}")
                continue
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                        if mod.startswith("app.engines."):
                            violations.append(f"{p.relative_to(ROOT)} imports {mod}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if mod.startswith("app.engines."):
                        violations.append(f"{p.relative_to(ROOT)} imports {mod}")
    # Domains are expected to be thin registry/specification surfaces. If they
    # become executable implementations, the dependency rule must be reviewed.
    for item in violations:
        warn("architecture review: " + item)


def check_migration_chain() -> None:
    versions = ROOT / "alembic" / "versions"
    revs: dict[str, str | None] = {}
    for p in versions.glob("*.py"):
        text = p.read_text(errors="ignore")
        rm = re.search(r"revision\s*=\s*['\"]([^'\"]+)", text)
        dm = re.search(r"down_revision\s*=\s*['\"]([^'\"]+)['\"]", text)
        if rm:
            revs[rm.group(1)] = dm.group(1) if dm else None
    if not revs:
        fail("no Alembic revisions discovered")
        return
    heads = sorted(set(revs) - {d for d in revs.values() if d})
    if len(heads) != 1:
        fail(f"unexpected Alembic head(s): {heads}")
        return
    seen: set[str] = set()
    cur = heads[0]
    while cur:
        if cur in seen:
            fail("Alembic chain contains a cycle")
            break
        seen.add(cur)
        cur = revs.get(cur)
        if cur is None:
            break
        if cur not in revs:
            fail(f"Alembic chain points to missing revision: {cur}")
            break
    if len(seen) != len(revs):
        fail(f"Alembic chain does not cover all revisions: chain={len(seen)}, files={len(revs)}")


def main() -> int:
    check_required_files()
    check_forbidden_files()
    check_obvious_secrets()
    check_architecture_boundaries()
    check_migration_chain()
    print("Hussam NextGen Unified Platform clean-baseline audit")
    print(f"repository: {ROOT}")
    print(f"failures: {len(FAILURES)}")
    print(f"warnings: {len(WARNINGS)}")
    for w in WARNINGS:
        print(f"WARNING: {w}")
    for f in FAILURES:
        print(f"FAIL: {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
