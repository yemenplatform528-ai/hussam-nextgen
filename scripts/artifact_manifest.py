#!/usr/bin/env python3
"""Create a deterministic SHA-256 manifest for a release artifact tree."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
out = Path(sys.argv[2] if len(sys.argv) > 2 else "release-manifest.json").resolve()
excluded = {".git", "__pycache__", ".pytest_cache"}
files=[]
for p in sorted(root.rglob("*")):
    if not p.is_file() or any(part in excluded for part in p.relative_to(root).parts):
        continue
    if p == out:
        continue
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    files.append({"path": str(p.relative_to(root)), "sha256": h, "bytes": p.stat().st_size})

source_hash = hashlib.sha256()
for item in files:
    rel = item["path"].encode("utf-8")
    data = (root / item["path"]).read_bytes()
    source_hash.update(len(rel).to_bytes(8, "big"))
    source_hash.update(rel)
    source_hash.update(len(data).to_bytes(8, "big"))
    source_hash.update(data)

try:
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
except (OSError, subprocess.CalledProcessError):
    source_commit = ""

if not source_commit:
    raise SystemExit("release manifest requires a Git repository commit")

payload={
    "format":"hussam-release-manifest/v1",
    "source_commit":source_commit,
    "source_manifest_hash":source_hash.hexdigest(),
    "file_count":len(files),
    "files":files
}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(f"release manifest: PASS ({len(files)} files) -> {out}")
