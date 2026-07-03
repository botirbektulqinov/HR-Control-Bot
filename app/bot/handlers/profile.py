from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select

from app.db.models import Attendance
from app.i18n import status_label, t, texts
from app.services.punch import branch_tz


def _hm(when, tz_name: str) -> str:
    return when.astimezone(ZoneInfo(tz_name)).strftime("%H:%M") if when else "—"

router = Router()


@router.message(F.text.in_(texts("menu_profile")))
async def show_profile(message: Message, employee, lang, **_):
    if employee is None:
        await message.answer(t(lang, "ask_jshshir"))
        return
    await message.answer(
        t(lang, "profile_card",
          name=employee.full_name,
          position=employee.position or "—",
          department=employee.department or "—",
          branch=employee.branch.name if employee.branch else "—",
          schedule=employee.schedule.name if employee.schedule else "—"),
    )


@router.message(F.text.in_(texts("menu_history")))
async def show_history(message: Message, employee, lang, session, **_):
    if employee is None:
        await message.answer(t(lang, "ask_jshshir"))
        return
    rows = (
        await session.scalars(
            select(Attendance)
            .where(Attendance.employee_id == employee.id)
            .order_by(Attendance.work_date.desc())
            .limit(7)
        )
    ).all()
    if not rows:
        await message.answer(t(lang, "history_empty"))
        return

    tz = branch_tz(employee)
    lines = [t(lang, "history_title")]
    for r in rows:
        extra = f" (+{r.late_minutes}′)" if r.late_minutes else ""
        lines.append(
            f"{r.work_date}  {_hm(r.check_in_at, tz)}–{_hm(r.check_out_at, tz)}  "
            f"{status_label(lang, r.status)}{extra}"
        )
    await message.answer("\n".join(lines))
