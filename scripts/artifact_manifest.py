#!/usr/bin/env python3
"""Create a deterministic SHA-256 manifest for a release artifact tree."""
from __future__ import annotations
import hashlib, json
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
payload={"format":"hussam-release-manifest/v1","file_count":len(files),"files":files}
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(f"release manifest: PASS ({len(files)} files) -> {out}")
