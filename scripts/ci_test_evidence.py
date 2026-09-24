#!/usr/bin/env python3
"""Create deterministic, source-bound CI evidence for Hussam NextGen.

The source manifest hash is computed from the Git-tracked repository files that
are present in the CI checkout. It is deliberately distinct from any
DeveloperExtensionVersion.source_hash unless the extension source artifact is
defined to be exactly this manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("CI_EVIDENCE_OUTPUT", "/tmp/hussam-ci-evidence.json"))


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
    )
    return [ROOT / p.decode("utf-8") for p in raw.split(b"\0") if p]


def source_manifest_hash(files: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(files, key=lambda p: p.relative_to(ROOT).as_posix()):
        rel = path.relative_to(ROOT).as_posix().encode("utf-8")
        data = path.read_bytes()
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def main() -> None:
    files = tracked_files()
    evidence = {
        "schema_version": "1.0",
        "evidence_type": "trusted_ci_test_evidence",
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "commit_sha": os.environ.get("GITHUB_SHA", ""),
        "ref": os.environ.get("GITHUB_REF", ""),
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "status": "passed",
        "source_manifest_hash": source_manifest_hash(files),
        "tracked_file_count": len(files),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print(json.dumps({"evidence": str(OUT), "evidence_sha256": digest, **evidence}, sort_keys=True))


if __name__ == "__main__":
    main()
