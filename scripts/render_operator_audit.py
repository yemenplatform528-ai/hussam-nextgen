#!/usr/bin/env python3
"""Read-only inventory for one explicitly selected Render workspace.

Never prints API credentials, arbitrary API response bodies, env-var values,
connection strings, or resources from other workspaces.
"""
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
        raise RenderAPIError(f"Render API returned HTTP {exc.code} for {path}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RenderAPIError(f"Render API request failed for {path}: {type(exc).__name__}") from None


def unwrap(item: dict) -> dict:
    for key in ("workspace", "service", "postgres", "keyValue"):
        if isinstance(item.get(key), dict):
            return item[key]
    return item


def list_pages(path: str):
    rows = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        payload = get_json(path, params)
        if not isinstance(payload, list):
            raise RenderAPIError(f"Unexpected response shape for {path}")
        rows.extend(unwrap(item) for item in payload if isinstance(item, dict))
        if len(payload) < PAGE_SIZE:
            break
        next_cursor = payload[-1].get("cursor") if payload and isinstance(payload[-1], dict) else None
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return rows


def owner_id(obj: dict):
    value = obj.get("ownerId") or obj.get("owner_id")
    if value:
        return value
    owner = obj.get("owner")
    if isinstance(owner, dict):
        return owner.get("id")
    return None


def pick(obj: dict, *keys):
    return {key: obj[key] for key in keys if key in obj and obj[key] is not None}


def audit():
    started = time.time()
    target = os.environ.get("RENDER_AUDIT_WORKSPACE_ID", "").strip()
    if not target:
        raise RenderAPIError("RENDER_AUDIT_WORKSPACE_ID is not configured")

    workspace_rows = list_pages("/workspaces")
    workspace = next((w for w in workspace_rows if w.get("id") == target), None)
    if not workspace:
        raise RenderAPIError("Configured workspace was not returned by Render; refusing to inventory")

    # Render API keys can see multiple workspaces. Filter every resource to the
    # single owner-selected workspace before building any report.
    all_services = list_pages("/services")
    all_databases = list_pages("/postgres")
    all_key_values = list_pages("/key-value")
    services = [x for x in all_services if owner_id(x) == target]
    databases = [x for x in all_databases if owner_id(x) == target]
    key_values = [x for x in all_key_values if owner_id(x) == target]

    safe_services = []
    for s in services:
        detail = s.get("serviceDetails") if isinstance(s.get("serviceDetails"), dict) else {}
        safe_services.append({
            **pick(s, "id", "name", "type", "branch", "repo", "autoDeploy", "createdAt", "updatedAt", "suspended", "dashboardUrl"),
            "url": detail.get("url"),
            "region": detail.get("region"),
            "plan": detail.get("plan"),
            "runtime": detail.get("runtime") or detail.get("env"),
        })

    safe_databases = [
        {
            **pick(d, "id", "name", "status", "plan", "region", "version", "expiresAt", "suspended", "createdAt", "updatedAt"),
            "ipAllowListEntryCount": len(d.get("ipAllowList") or []),
        }
        for d in databases
    ]
    safe_kv = [
        {**pick(k, "id", "name", "plan", "region", "status", "suspended", "createdAt", "updatedAt")}
        for k in key_values
    ]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "scope": "single_workspace",
        "workspace": pick(workspace, "id", "name", "type"),
        "counts": {
            "services": len(safe_services),
            "postgres": len(safe_databases),
            "key_value": len(safe_kv),
        },
        "services": sorted(safe_services, key=lambda x: str(x.get("name", ""))),
        "postgres": sorted(safe_databases, key=lambda x: str(x.get("name", ""))),
        "key_value": sorted(safe_kv, key=lambda x: str(x.get("name", ""))),
        "elapsed_seconds": round(time.time() - started, 3),
        "security_note": "Only the selected workspace is included. No secrets, env-var values, connection strings, or arbitrary API response bodies are recorded.",
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
