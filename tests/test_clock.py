# Desk clock tests | Built by Haryan Patel, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Store UTC, show Saskatchewan time (UTC-6 all year). The weekly report depends on these rules."""
from datetime import date, datetime, timedelta, timezone

from app.core import clock


def test_late_evening_is_still_today_at_the_desk():
    # 4:30 a.m. UTC on 15 Oct is 10:30 p.m. on 14 Oct in Saskatoon
    assert clock.local_date(datetime(2026, 10, 15, 4, 30, tzinfo=timezone.utc)) == date(2026, 10, 14)


def test_week_starts_on_monday():
    assert clock.week_start(date(2026, 10, 18)) == date(2026, 10, 12)  # Sunday -> Monday before
    assert clock.week_start(date(2026, 10, 12)) == date(2026, 10, 12)  # Monday stays Monday


def test_local_desk_time_is_stored_as_utc():
    assert clock.local_at(date(2026, 10, 14), "12:40") == datetime(2026, 10, 14, 18, 40, tzinfo=timezone.utc)


def test_times_are_shown_the_way_staff_say_them():
    assert clock.fmt_time(datetime(2026, 10, 14, 18, 40, tzinfo=timezone.utc)) == "12:40 p.m."
    assert clock.fmt_time(datetime(2026, 10, 14, 6, 5, tzinfo=timezone.utc)) == "12:05 a.m."
    assert clock.minutes(timedelta(minutes=7, seconds=30)) == 7.5
