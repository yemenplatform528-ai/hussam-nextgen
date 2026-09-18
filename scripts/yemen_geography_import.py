#!/usr/bin/env python3
"""Validate and optionally import a Yemen market geography dataset.

The platform deliberately does not embed a hand-authored national geography list.
This tool accepts an externally sourced, reviewed dataset and enforces the
market-scoped hierarchy before any database mutation.

CSV columns:
code,level,name,name_ar,parent_code,status,metadata_json

Levels: country, governorate, district, locality
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.models.market import MarketContext, MarketGeography

LEVELS = ("country", "governorate", "district", "locality")
PARENT_LEVEL = {"country": None, "governorate": "country", "district": "governorate", "locality": "district"}
REQUIRED = {"code", "level", "name", "parent_code"}


@dataclass(frozen=True)
class GeographyRow:
    code: str
    level: str
    name: str
    name_ar: str | None
    parent_code: str | None
    status: str
    metadata_json: str


def load_rows(path: Path) -> list[GeographyRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED - fields
        if missing:
            raise ValueError(f"missing required CSV columns: {sorted(missing)}")
        rows: list[GeographyRow] = []
        for line_no, raw in enumerate(reader, start=2):
            code = (raw.get("code") or "").strip()
            level = (raw.get("level") or "").strip()
            name = (raw.get("name") or "").strip()
            parent = (raw.get("parent_code") or "").strip() or None
            name_ar = (raw.get("name_ar") or "").strip() or None
            status = (raw.get("status") or "active").strip()
            metadata = (raw.get("metadata_json") or "{}").strip() or "{}"
            if not code or not level or not name:
                raise ValueError(f"line {line_no}: code, level and name are required")
            if level not in LEVELS:
                raise ValueError(f"line {line_no}: invalid level {level!r}")
            if (level == "country") != (parent is None):
                raise ValueError(f"line {line_no}: country must have no parent; non-country must have parent")
            if status not in {"active", "inactive"}:
                raise ValueError(f"line {line_no}: invalid status {status!r}")
            try:
                json.loads(metadata)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_no}: metadata_json is not valid JSON: {exc}") from exc
            rows.append(GeographyRow(code, level, name, name_ar, parent, status, metadata))
    return rows


def validate_rows(rows: list[GeographyRow]) -> None:
    if not rows:
        raise ValueError("dataset is empty")
    by_code: dict[str, GeographyRow] = {}
    for row in rows:
        if row.code in by_code:
            raise ValueError(f"duplicate geography code: {row.code}")
        by_code[row.code] = row
    roots = [r for r in rows if r.level == "country"]
    if len(roots) != 1:
        raise ValueError(f"dataset must contain exactly one country root; found {len(roots)}")
    root = roots[0]
    if root.code.upper() != "YE" and not root.code.upper().startswith("YE-"):
        raise ValueError("Yemen dataset country root code must be YE or a YE-prefixed reviewed code")
    for row in rows:
        expected_parent = PARENT_LEVEL[row.level]
        if expected_parent is None:
            continue
        parent = by_code.get(row.parent_code or "")
        if parent is None:
            raise ValueError(f"{row.code}: parent_code {row.parent_code!r} does not exist")
        if parent.level != expected_parent:
            raise ValueError(f"{row.code}: parent {parent.code} must be level {expected_parent}")


def import_rows(session: Session, market: MarketContext, rows: list[GeographyRow], apply: bool) -> int:
    existing = {g.code: g for g in session.scalars(select(MarketGeography).where(MarketGeography.market_id == market.id)).all()}
    by_code: dict[str, GeographyRow] = {r.code: r for r in rows}
    ordered = sorted(rows, key=lambda r: LEVELS.index(r.level))
    changed = 0
    ids: dict[str, int] = {}
    for row in ordered:
        obj = existing.get(row.code)
        parent_id = ids.get(row.parent_code) if row.parent_code else None
        if obj is None:
            obj = MarketGeography(market_id=market.id, code=row.code)
            session.add(obj)
        obj.parent_id = parent_id
        obj.level = row.level
        obj.name = row.name
        obj.name_ar = row.name_ar
        obj.status = row.status
        obj.metadata_json = row.metadata_json
        session.flush()
        ids[row.code] = obj.id
        changed += 1
    if apply:
        session.commit()
    else:
        session.rollback()
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="reviewed geography CSV")
    parser.add_argument("--database-url", default="sqlite+pysqlite:////tmp/hussam-yemen-geography.db")
    parser.add_argument("--market-code", default="YE")
    parser.add_argument("--apply", action="store_true", help="commit changes; default is dry-run")
    args = parser.parse_args()

    rows = load_rows(args.input)
    validate_rows(rows)
    engine = create_engine(args.database_url, future=True)
    with Session(engine) as session:
        market = session.scalar(select(MarketContext).where(MarketContext.code == args.market_code))
        if market is None:
            raise SystemExit(f"market {args.market_code!r} does not exist; create/configure it first")
        changed = import_rows(session, market, rows, args.apply)
    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(json.dumps({"status": "PASS", "mode": mode, "market": args.market_code, "rows": len(rows), "rows_processed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
