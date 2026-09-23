#!/usr/bin/env python3
"""External runtime smoke test for the deployed FastAPI Cloud staging app.

This intentionally verifies only public, non-secret endpoints. It does not
attempt to bypass readiness gates or fabricate production configuration.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


def request(url: str, timeout: float = 15.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "hussam-nextgen-runtime-smoke/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read(4096).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4096).decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hussam-nextgen.fastapicloud.dev")
    parser.add_argument("--attempts", type=int, default=20)
    parser.add_argument("--delay", type=float, default=15.0)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    checks = ("/health", "/openapi.json", "/docs")
    last: dict[str, object] = {}

    for attempt in range(1, args.attempts + 1):
        last = {}
        all_ok = True
        for path in checks:
            try:
                status, body = request(base + path)
                last[path] = {"status": status, "sample": body[:160]}
                if status != 200:
                    all_ok = False
            except Exception as exc:
                last[path] = {"error": f"{type(exc).__name__}: {exc}"}
                all_ok = False

        print(json.dumps({"attempt": attempt, "checks": last}, ensure_ascii=False))
        if all_ok:
            print("EXTERNAL_RUNTIME_SMOKE_OK")
            return 0
        if attempt < args.attempts:
            time.sleep(args.delay)

    print(json.dumps({"result": "EXTERNAL_RUNTIME_SMOKE_FAILED", "last": last}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
