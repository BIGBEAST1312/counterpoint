# Feature 4 · Weekly report & trends | Owner: Haryan Patel
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
"""Pure statistics functions. They take plain `Row`s, not database objects, so tests need no database.

  totals()        US-20  walk-ups, served, walk-aways, median and 90th-percentile wait
  heatmap()       US-21  arrivals by day and hour
(compare() for US-23 and problem_types() for US-24 come in Product v2.)
"""
import statistics
from dataclasses import dataclass
from datetime import datetime

from app.core.config import LOCAL_TZ

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS = list(range(9, 21))  # columns 9 a.m. ... 8 p.m. (the 8-9 p.m. hour), fixed so no desk-hours data is needed


@dataclass(frozen=True)
class Row:
    """One past visit, reduced to what the report needs. No names, no ticket numbers."""
    arrived_at: datetime
    called_at: datetime | None
    served: bool          # True if the student was helped (status done)
    problem_type: str

    @property
    def wait_min(self) -> float | None:
        if not self.served or self.called_at is None:
            return None
        return (self.called_at - self.arrived_at).total_seconds() / 60

    @property
    def local_arrival(self) -> datetime:
        return self.arrived_at.astimezone(LOCAL_TZ)


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile: the smallest value that `pct`% of the data is at or below.
    For waits 5, 8, 10, 12, 30 the 90th percentile is the 5th value (ceil(0.9 x 5) = 5): 30."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * pct // 100))  # ceil without importing math
    return round(ordered[int(rank) - 1], 1)


def totals(rows: list[Row]) -> dict:
    """US-20. Walk-aways are students never served (missed their call or left the line);
    their time is left out of the wait figures (test 3)."""
    waits = [r.wait_min for r in rows if r.wait_min is not None]
    served = sum(r.served for r in rows)
    walkups = len(rows)
    walkaways = walkups - served
    return {"walk_ups": walkups, "served": served, "walk_aways": walkaways,
            "walk_away_pct": round(walkaways / walkups * 100, 1) if walkups else None,
            "median_wait": median(waits), "p90_wait": percentile(waits, 90)}


def heatmap(rows: list[Row]) -> dict:
    """US-21: one row per day Mon-Sun, one column per hour 9 a.m.-9 p.m."""
    grid = [[0] * len(HOURS) for _ in DAY_NAMES]
    for r in rows:
        t = r.local_arrival
        if t.hour in HOURS:
            grid[t.weekday()][HOURS.index(t.hour)] += 1
    peak = max(((d, h, c) for d, row in enumerate(grid) for h, c in enumerate(row)), key=lambda x: x[2], default=None)
    return {"hours": HOURS, "rows": [{"day": DAY_NAMES[i], "counts": grid[i]} for i in range(7)],
            "max": max((c for row in grid for c in row), default=0),
            "peak": None if not peak or peak[2] == 0 else {"day": DAY_NAMES[peak[0]], "hour": HOURS[peak[1]], "count": peak[2]}}
