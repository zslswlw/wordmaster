import os
from datetime import date, datetime, time, timedelta, timezone
from threading import Lock
from typing import Optional
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "Asia/Shanghai"


class BusinessClock:
    def __init__(self, timezone_name: Optional[str] = None):
        self.timezone_name = timezone_name or os.getenv("APP_TIMEZONE", DEFAULT_TIMEZONE)
        self.timezone = ZoneInfo(self.timezone_name)

    def now(self) -> datetime:
        return datetime.now(timezone.utc).astimezone(self.timezone)

    def today(self) -> date:
        return self.now().date()

    def utcnow(self) -> datetime:
        """Return a naive UTC datetime for the existing SQLite schema."""
        return self.now().astimezone(timezone.utc).replace(tzinfo=None)

    def local_day_bounds_utc(self, day: Optional[date] = None) -> tuple[datetime, datetime]:
        target = day or self.today()
        local_start = datetime.combine(target, time.min, tzinfo=self.timezone)
        local_end = local_start + timedelta(days=1)
        return (
            local_start.astimezone(timezone.utc).replace(tzinfo=None),
            local_end.astimezone(timezone.utc).replace(tzinfo=None),
        )


class MutableBusinessClock(BusinessClock):
    def __init__(self, timezone_name: Optional[str] = None, initial: Optional[datetime] = None):
        super().__init__(timezone_name)
        self._lock = Lock()
        self._current: Optional[datetime] = None
        if initial is not None:
            self.set(initial)

    def now(self) -> datetime:
        with self._lock:
            if self._current is not None:
                return self._current
        return super().now()

    def set(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=self.timezone)
        value = value.astimezone(self.timezone)
        with self._lock:
            self._current = value
        return value

    def advance(self, *, days: int = 0, minutes: int = 0) -> datetime:
        with self._lock:
            current = self._current
            if current is None:
                current = datetime.now(timezone.utc).astimezone(self.timezone)
            self._current = current + timedelta(days=days, minutes=minutes)
            return self._current

    def reset(self) -> datetime:
        with self._lock:
            self._current = None
        return self.now()


_active_clock: BusinessClock = BusinessClock()


def get_clock() -> BusinessClock:
    return _active_clock


def set_clock(clock: BusinessClock) -> None:
    global _active_clock
    _active_clock = clock


def enable_test_clock(initial: Optional[datetime] = None) -> MutableBusinessClock:
    clock = MutableBusinessClock(initial=initial)
    set_clock(clock)
    return clock


def get_test_clock() -> MutableBusinessClock:
    if not isinstance(_active_clock, MutableBusinessClock):
        raise RuntimeError("Mutable clock is only available in test mode")
    return _active_clock


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
