"""Attendance status hisoblash (jadval + haqiqiy vaqt bo'yicha).

Vaqtlar DB'da timezone-aware UTC saqlanadi; hisob-kitob filial timezone'ida
(zoneinfo) bajariladi.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.constants import VERY_LATE_THRESHOLD_MIN, Status

if TYPE_CHECKING:  # runtime'da ORM'ga bog'lanmaymiz (duck-typed: workday_set/time'lar)
    from app.db.models import WorkSchedule


def _local(when: dt.datetime, tz_name: str) -> dt.datetime:
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(ZoneInfo(tz_name))


def is_workday(schedule: WorkSchedule, when: dt.datetime, tz_name: str) -> bool:
    return _local(when, tz_name).isoweekday() in schedule.workday_set()


def evaluate_check_in(
    schedule: WorkSchedule, when: dt.datetime, tz_name: str
) -> tuple[str, int]:
    """(status, late_minutes) qaytaradi."""
    local = _local(when, tz_name)
    if local.isoweekday() not in schedule.workday_set():
        return Status.WEEKEND.value, 0

    start = dt.datetime.combine(local.date(), schedule.start_time, tzinfo=local.tzinfo)
    delta_min = (local - start).total_seconds() / 60

    if delta_min <= schedule.grace_minutes:
        return Status.ON_TIME.value, 0
    if delta_min <= VERY_LATE_THRESHOLD_MIN:
        return Status.LATE.value, round(delta_min)
    return Status.VERY_LATE.value, round(delta_min)


def evaluate_check_out(
    schedule: WorkSchedule,
    check_in_at: dt.datetime,
    when: dt.datetime,
    tz_name: str,
) -> tuple[int, int, int]:
    """(early_leave_minutes, worked_minutes, overtime_minutes)."""
    local = _local(when, tz_name)
    end = dt.datetime.combine(local.date(), schedule.end_time, tzinfo=local.tzinfo)

    early_leave = max(0, round((end - local).total_seconds() / 60))
    overtime = max(0, round((local - end).total_seconds() / 60))
    worked = max(0, round((when - check_in_at).total_seconds() / 60))
    return early_leave, worked, overtime


if __name__ == "__main__":
    class _Sched:  # ORM'siz stub (self-check mustaqil ishlashi uchun)
        start_time, end_time, grace_minutes = dt.time(9, 0), dt.time(18, 0), 5
        def workday_set(self):
            return {1, 2, 3, 4, 5}

    sched = _Sched()
    tz = "Asia/Tashkent"

    def at(h, m):  # Tashkent local -> UTC (Tashkent = UTC+5)
        return dt.datetime(2026, 7, 6, h - 5, m, tzinfo=dt.timezone.utc)  # Mon

    assert evaluate_check_in(sched, at(9, 3), tz) == (Status.ON_TIME.value, 0)
    assert evaluate_check_in(sched, at(9, 20), tz)[0] == Status.LATE.value
    assert evaluate_check_in(sched, at(11, 0), tz)[0] == Status.VERY_LATE.value
    # Yakshanba
    sun = dt.datetime(2026, 7, 5, 4, 0, tzinfo=dt.timezone.utc)
    assert evaluate_check_in(sched, sun, tz) == (Status.WEEKEND.value, 0)

    el, worked, ot = evaluate_check_out(sched, at(9, 0), at(17, 30), tz)
    assert el == 30 and ot == 0 and worked == 510, (el, worked, ot)
    el, worked, ot = evaluate_check_out(sched, at(9, 0), at(19, 0), tz)
    assert el == 0 and ot == 60, (el, ot)
    print("attendance ok")
