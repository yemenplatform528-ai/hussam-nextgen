from datetime import datetime, timezone

import pytest

from app.runner.cron import next_cron_occurrence


def test_cron_adapter_returns_next_utc_occurrence():
    after = datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc)
    result = next_cron_occurrence("30 9 * * *", "Asia/Aden", after)
    assert result == datetime(2026, 11, 24, 6, 30, tzinfo=timezone.utc)


def test_cron_adapter_rejects_naive_datetime():
    with pytest.raises(ValueError):
        next_cron_occurrence("0 * * * *", "UTC", datetime(2026, 11, 24, 8, 0))


def test_cron_adapter_rejects_unknown_timezone():
    with pytest.raises(ValueError):
        next_cron_occurrence("0 * * * *", "Mars/Olympus", datetime.now(timezone.utc))


def test_cron_adapter_preserves_local_wall_clock_across_spring_forward():
    after = datetime(2026, 3, 7, 14, 0, tzinfo=timezone.utc)
    result = next_cron_occurrence("0 9 * * *", "America/New_York", after)
    assert result == datetime(2026, 3, 8, 13, 0, tzinfo=timezone.utc)


def test_cron_adapter_preserves_local_wall_clock_across_fall_back():
    after = datetime(2026, 10, 31, 13, 0, tzinfo=timezone.utc)
    result = next_cron_occurrence("0 9 * * *", "America/New_York", after)
    assert result == datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc)
