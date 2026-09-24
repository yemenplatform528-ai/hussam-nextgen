#!/usr/bin/env python3
"""Fail-closed final release gate."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence-manifest", type=Path, required=True)
    p.add_argument("--release-manifest", type=Path, required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--ci-evidence", type=Path)
    args = p.parse_args()

    evidence = json.loads(args.evidence_manifest.read_text(encoding="utf-8"))
    if evidence.get("closed") != 10 or evidence.get("pending_external") != 0:
        raise SystemExit(f"FAIL: external evidence is not 10/10 closed (closed={evidence.get('closed')}, pending={evidence.get('pending_external')})")

    manifest = json.loads(args.release_manifest.read_text(encoding="utf-8"))
    if manifest.get("format") != "hussam-release-manifest/v1" or not manifest.get("files"):
        raise SystemExit("FAIL: release manifest is missing or invalid")

    if args.ci_evidence:
        ci = json.loads(args.ci_evidence.read_text(encoding="utf-8"))
        if ci.get("status") != "passed":
            raise SystemExit("FAIL: trusted CI evidence is not passed")
        if ci.get("commit_sha") != args.expected_commit:
            raise SystemExit("FAIL: CI evidence commit does not match expected release commit")
        if not ci.get("run_id") or not ci.get("source_manifest_hash"):
            raise SystemExit("FAIL: CI evidence lacks run identity/source hash")

    print("FINAL_RELEASE_GATE=PASS")
    print(f"commit={args.expected_commit}")
    print(f"external_gates={evidence['closed']}/10")
    print(f"release_files={manifest['file_count']}")
    print(f"evidence_manifest_sha256={sha256(args.evidence_manifest)}")
    print(f"release_manifest_sha256={sha256(args.release_manifest)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
