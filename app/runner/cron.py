"""Timezone-aware cron adapter for the portable scheduler."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def next_cron_occurrence(expression: str, timezone_name: str, after: datetime) -> datetime:
    """Return the next UTC occurrence using croniter and an IANA timezone."""
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone must be a valid IANA timezone") from exc
    if after.tzinfo is None:
        raise ValueError("after must be timezone-aware")
    try:
        from croniter import croniter
    except ImportError as exc:
        raise RuntimeError("install hussam-nextgen[runner] to enable cron schedules") from exc
    local_base = after.astimezone(zone)
    result = croniter(expression, local_base).get_next(datetime)
    if result.tzinfo is None:
        raise ValueError("cron adapter returned a naive datetime")
    return result.astimezone(timezone.utc)
