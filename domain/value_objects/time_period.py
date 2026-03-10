"""
TimePeriod Value Object

Defines analysis windows for rolling metrics (30/90/180-day breakdowns).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC


@dataclass(frozen=True)
class TimePeriod:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError("TimePeriod start must be before end")

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def contains(self, dt: datetime) -> bool:
        return self.start <= dt <= self.end

    @staticmethod
    def last_n_days(n: int) -> TimePeriod:
        end = datetime.now(UTC)
        start = end - timedelta(days=n)
        return TimePeriod(start=start, end=end)

    @staticmethod
    def rolling_windows() -> list[TimePeriod]:
        """Standard 30/90/180 day windows for trend analysis."""
        return [TimePeriod.last_n_days(n) for n in (30, 90, 180)]
