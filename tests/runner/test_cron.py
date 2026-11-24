from datetime import datetime, timezone

import pytest

from app.runner.cron import next_cron_occurrence


def test_cron_adapter_returns_next_utc_occurrence():
    after = datetime(2026, 11, 24, 8, 0, tzinfo=timezone.utc)
    result = next_cron_occurrence("30 9 * * *", "Asia/Aden", after)
    assert result == datetime(2026, 11, 24, 6, 30, tzinfo=timezone.utc)


def test_cron_adapter_rejects_naive_datetime():
    with pytest.raises(ValueError):
        next_cron_occurrence("0 * * * *", "UTC", datetime(2026, 11, 24, 8, 0))


def test_cron_adapter_rejects_unknown_timezone():
    with pytest.raises(ValueError):
        next_cron_occurrence("0 * * * *", "Mars/Olympus", datetime.now(timezone.utc))
