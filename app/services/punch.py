from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Attendance, Employee
from app.services.attendance import evaluate_check_in, evaluate_check_out
from app.services.location import LocationCheck


def _work_date(when: dt.datetime, tz_name: str) -> dt.date:
    return when.astimezone(ZoneInfo(tz_name)).date()


def branch_tz(employee: Employee) -> str:
    return employee.branch.timezone if employee.branch else "Asia/Tashkent"


async def get_today(session: AsyncSession, employee: Employee) -> Attendance | None:
    wd = _work_date(dt.datetime.now(dt.timezone.utc), branch_tz(employee))
    return await session.scalar(
        select(Attendance).where(
            Attendance.employee_id == employee.id, Attendance.work_date == wd
        )
    )


async def record_check_in(
    session: AsyncSession, employee: Employee, loc: LocationCheck, when: dt.datetime
) -> Attendance:
    tz = branch_tz(employee)
    status, late = evaluate_check_in(employee.schedule, when, tz)
    row = await get_today(session, employee)
    if row is None:
        row = Attendance(
            employee_id=employee.id,
            branch_id=employee.branch_id,
            work_date=_work_date(when, tz),
        )
        session.add(row)
    row.check_in_at = when
    row.check_in_lat = loc.lat
    row.check_in_lon = loc.lon
    row.check_in_accuracy = loc.accuracy
    row.check_in_distance_m = round(loc.distance_m, 1)
    row.status = status
    row.late_minutes = late
    if loc.warnings:
        row.flags = json.dumps({"check_in": loc.warnings}, ensure_ascii=False)
    return row


async def record_check_out(
    session: AsyncSession, employee: Employee, loc: LocationCheck, when: dt.datetime
) -> Attendance:
    tz = branch_tz(employee)
    row = await get_today(session, employee)
    if row is None or row.check_in_at is None:
        raise ValueError("not_checked_in")
    early, worked, overtime = evaluate_check_out(
        employee.schedule, row.check_in_at, when, tz
    )
    row.check_out_at = when
    row.check_out_lat = loc.lat
    row.check_out_lon = loc.lon
    row.check_out_accuracy = loc.accuracy
    row.check_out_distance_m = round(loc.distance_m, 1)
    row.early_leave_minutes = early
    row.worked_minutes = worked
    row.overtime_minutes = overtime
    if loc.warnings:
        flags = json.loads(row.flags) if row.flags else {}
        flags["check_out"] = loc.warnings
        row.flags = json.dumps(flags, ensure_ascii=False)
    return row
