#!/usr/bin/env python3
"""Read-only Render account audit. Never prints API credentials or arbitrary response bodies."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.render.com/v1"
TIMEOUT = 20
MAX_PAGES = 10
PAGE_SIZE = 100


class RenderAPIError(RuntimeError):
    pass


def get_json(path: str, query: dict | None = None):
    token = os.environ.get("RENDER_API_KEY", "").strip()
    if not token:
        raise RenderAPIError("RENDER_API_KEY is not configured")
    url = API + path
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
            "User-Agent": "yemen-render-readonly-audit/1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not include response bodies or headers; they may contain sensitive details.
        raise RenderAPIError(f"Render API returned HTTP {exc.code} for {path}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RenderAPIError(f"Render API request failed for {path}: {type(exc).__name__}") from None


def list_pages(path: str):
    rows = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        payload = get_json(path, params)
        if isinstance(payload, list):
            # Render list endpoints may wrap each resource as {cursor, service}.
            for item in payload:
                if isinstance(item, dict):
                    resource = item.get("service") or item.get("postgres") or item.get("keyValue") or item
                    if isinstance(resource, dict):
                        rows.append(resource)
            if len(payload) < PAGE_SIZE:
                break
            # Some endpoint responses do not expose a cursor; do not loop the same page.
            next_cursor = payload[-1].get("cursor") if payload and isinstance(payload[-1], dict) else None
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        else:
            raise RenderAPIError(f"Unexpected response shape for {path}")
    return rows


def pick(obj: dict, *keys):
    return {key: obj[key] for key in keys if key in obj and obj[key] is not None}


def audit():
    started = time.time()
    workspaces = get_json("/workspaces")
    services = list_pages("/services")
    databases = list_pages("/postgres")
    key_values = list_pages("/key-value")

    safe_services = []
    for s in services:
        detail = s.get("serviceDetails") if isinstance(s.get("serviceDetails"), dict) else {}
        safe_services.append({
            **pick(s, "id", "name", "type", "ownerId", "branch", "repo", "autoDeploy", "createdAt", "updatedAt", "suspended", "dashboardUrl"),
            "url": detail.get("url"),
            "region": detail.get("region"),
            "plan": detail.get("plan"),
            "runtime": detail.get("runtime") or detail.get("env"),
            "rootDir": detail.get("rootDir"),
        })

    safe_databases = [
        {
            **pick(d, "id", "name", "ownerId", "status", "plan", "region", "version", "expiresAt", "suspended", "createdAt", "updatedAt"),
            "ipAllowListEntryCount": len(d.get("ipAllowList") or []),
        }
        for d in databases
    ]
    safe_kv = [
        {**pick(k, "id", "name", "ownerId", "plan", "region", "status", "suspended", "createdAt", "updatedAt")}
        for k in key_values
    ]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "api": "https://api.render.com/v1",
        "workspaces": [
            pick(w, "id", "name", "type")
            for item in (workspaces if isinstance(workspaces, list) else [])
            for w in ([item.get("workspace", item)] if isinstance(item, dict) else [])
            if isinstance(w, dict)
        ],
        "counts": {
            "services": len(safe_services),
            "postgres": len(safe_databases),
            "key_value": len(safe_kv),
        },
        "services": sorted(safe_services, key=lambda x: str(x.get("name", ""))),
        "postgres": sorted(safe_databases, key=lambda x: str(x.get("name", ""))),
        "key_value": sorted(safe_kv, key=lambda x: str(x.get("name", ""))),
        "elapsed_seconds": round(time.time() - started, 3),
        "security_note": "No secret values, connection strings, request bodies, or API response bodies are recorded.",
    }
    return report


def main():
    try:
        report = audit()
    except RenderAPIError as exc:
        print(json.dumps({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "mode": "READ_ONLY",
            "status": "BLOCKED",
            "error": str(exc),
        }, indent=2))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
