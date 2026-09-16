#!/usr/bin/env bash
set -euo pipefail
: "${BASE_URL:?BASE_URL is required, e.g. https://api.example.com}"
: "${OUTPUT_FILE:?OUTPUT_FILE is required}"
command -v curl >/dev/null || { echo "curl is required" >&2; exit 2; }
mkdir -p "$(dirname "$OUTPUT_FILE")"
python - "$BASE_URL" "$OUTPUT_FILE" <<'PY'
import json, subprocess, sys, time
from urllib.parse import urljoin
base = sys.argv[1].rstrip('/') + '/'
out = sys.argv[2]
results = {}
for name, path in (("health", "health"), ("ready", "ready?deep=true"), ("metrics", "metrics")):
    started = time.monotonic()
    p = subprocess.run(["curl", "-fsS", "--max-time", "15", urljoin(base, path)], text=True, capture_output=True)
    results[name] = {"ok": p.returncode == 0, "elapsed_seconds": round(time.monotonic()-started, 3), "body": p.stdout[:12000] if p.returncode == 0 else None}
    if p.returncode != 0:
        results[name]["error"] = p.stderr.strip()[:1000]
    if name == "ready" and p.returncode != 0:
        raise SystemExit("deep readiness probe failed")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"base_url": base, "captured_at_epoch": time.time(), "probes": results}, f, ensure_ascii=False, indent=2)
PY
printf 'OBSERVABILITY_PROBE=PASS\n'
