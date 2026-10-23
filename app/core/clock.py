# Shared infrastructure | Built by Haryan Patel, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Time helpers. Rule for the whole project: store UTC, convert to local time only to group or display."""
from datetime import date, datetime, time, timedelta, timezone

from .config import LOCAL_TZ


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime. Use this instead of datetime.now().

    Always call it as `clock.utcnow()` (module attribute), so tests can freeze time with
    monkeypatch.setattr(clock, "utcnow", lambda: some_time).
    """
    return datetime.now(timezone.utc)


def local_date(moment: datetime) -> date:
    """The desk's calendar date for a UTC moment (e.g. 11 p.m. in Saskatoon is still 'today')."""
    return moment.astimezone(LOCAL_TZ).date()


def local_today(now: datetime | None = None) -> date:
    return local_date(now or utcnow())


def local_midnight_utc(day: date) -> datetime:
    """Start of a local calendar day, expressed in UTC (for database range queries)."""
    return datetime.combine(day, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def week_start(day: date) -> date:
    """Monday of the week containing `day`."""
    return day - timedelta(days=day.weekday())


def minutes(delta: timedelta | None) -> float | None:
    return None if delta is None else round(delta.total_seconds() / 60, 1)


def local(moment: datetime) -> datetime:
    """A UTC moment shown in the desk's time zone."""
    return moment.astimezone(LOCAL_TZ)


def local_at(day: date, hhmm: str) -> datetime:
    """'13:15' on a local calendar day, as a UTC datetime."""
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m), tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def fmt_time(moment: datetime) -> str:
    """'1:15 p.m.' in local time, the way staff say it."""
    t = local(moment)
    hour = t.hour % 12 or 12
    return f"{hour}:{t.minute:02d} {'a.m.' if t.hour < 12 else 'p.m.'}"
