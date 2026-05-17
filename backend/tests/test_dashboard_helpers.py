"""Unit tests for the dashboard's pure helpers.

The HTTP routes are thin SQL wrappers, exercised by the docker-compose
integration smoke check. Here we lock in the bucketing + latency logic
that the routes depend on.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.v1.dashboard import _fill_daily_buckets, _mean_latency_ms


def test_fill_daily_buckets_emits_dense_range():
    now = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)
    buckets = _fill_daily_buckets([], now=now, days=7)
    assert len(buckets) == 7
    # Inclusive of today, so last entry is today's date
    assert buckets[-1] == {"date": "2026-05-17", "count": 0}
    # First entry is 6 days before today (days-1)
    assert buckets[0]["date"] == "2026-05-11"
    # All zero on empty input
    assert all(b["count"] == 0 for b in buckets)


def test_fill_daily_buckets_groups_timestamps_by_date():
    now = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)
    ts = [
        datetime(2026, 5, 17, 8, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 17, 22, 30, tzinfo=timezone.utc),  # same day
        datetime(2026, 5, 16, 1, 0, tzinfo=timezone.utc),
        datetime(2020, 1, 1, tzinfo=timezone.utc),  # well outside the window
    ]
    buckets = _fill_daily_buckets(ts, now=now, days=7)
    by_date = {b["date"]: b["count"] for b in buckets}
    assert by_date["2026-05-17"] == 2
    assert by_date["2026-05-16"] == 1
    # Out-of-window stamps don't pollute any visible bucket
    assert sum(by_date.values()) == 3


def test_mean_latency_ms_skips_nulls():
    pairs: list[tuple[datetime | None, datetime | None]] = [
        (
            datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 17, 12, 0, 0, 500_000, tzinfo=timezone.utc),
        ),  # 500 ms
        (
            datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 5, 17, 12, 0, 1, 500_000, tzinfo=timezone.utc),
        ),  # 1500 ms
        (None, datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)),  # skipped
        (datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc), None),  # skipped
    ]
    assert _mean_latency_ms(pairs) == 1000.0  # mean of 500 and 1500


def test_mean_latency_ms_handles_empty():
    assert _mean_latency_ms([]) == 0.0
