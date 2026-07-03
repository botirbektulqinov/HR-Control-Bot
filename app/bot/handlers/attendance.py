import datetime as dt
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards import location_kb, main_menu
from app.bot.states import Punch
from app.config import get_settings
from app.db.models import Employee
from app.i18n import status_label, t, texts
from app.services.location import LocationCheck, validate_location
from app.services.punch import branch_tz, get_today, record_check_in, record_check_out

router = Router()
settings = get_settings()

_REJECT = {
    "outside_radius": "loc_outside",
    "stale": "loc_stale",
    "forwarded": "loc_forwarded",
    "need_live": "loc_need_live",
    "no_location": "loc_none",
}


def _fmt(when: dt.datetime, tz_name: str) -> str:
    return when.astimezone(ZoneInfo(tz_name)).strftime("%H:%M")


async def _require_ready(message: Message, employee: Employee | None, lang: str) -> bool:
    if employee is None:
        await message.answer(t(lang, "ask_jshshir"))
        return False
    if not employee.branch or not employee.schedule:
        await message.answer(t(lang, "no_config"))
        return False
    return True


async def _reject(message: Message, lang: str, loc: LocationCheck, employee: Employee):
    key = _REJECT.get(loc.reason, "loc_none")
    if key == "loc_outside":
        text = t(lang, key, dist=int(loc.distance_m), radius=employee.branch.radius_m)
    else:
        text = t(lang, key)
    await message.answer(text, reply_markup=main_menu(lang, employee.is_admin))


@router.message(F.text.in_(texts("menu_check_in")))
async def ask_check_in(message, state: FSMContext, employee, lang, session, **_):
    if not await _require_ready(message, employee, lang):
        return
    today = await get_today(session, employee)
    if today and today.check_in_at:
        await message.answer(
            t(lang, "already_checked_in", time=_fmt(today.check_in_at, branch_tz(employee)))
        )
        return
    await state.set_state(Punch.waiting_location_in)
    await message.answer(t(lang, "send_location_in"), reply_markup=location_kb(lang))


@router.message(F.text.in_(texts("menu_check_out")))
async def ask_check_out(message, state: FSMContext, employee, lang, session, **_):
    if not await _require_ready(message, employee, lang):
        return
    today = await get_today(session, employee)
    if today is None or today.check_in_at is None:
        await message.answer(t(lang, "not_checked_in"))
        return
    if today.check_out_at:
        await message.answer(
            t(lang, "already_checked_out", time=_fmt(today.check_out_at, branch_tz(employee)))
        )
        return
    await state.set_state(Punch.waiting_location_out)
    await message.answer(t(lang, "send_location_out"), reply_markup=location_kb(lang))


@router.message(Punch.waiting_location_in, F.location)
async def do_check_in(message, state: FSMContext, employee, lang, session, **_):
    b = employee.branch
    loc = validate_location(
        message, b.latitude, b.longitude, b.radius_m,
        strictness=settings.location_strictness,
        max_age_seconds=settings.location_max_age_seconds,
    )
    await state.clear()
    if not loc.ok:
        await _reject(message, lang, loc, employee)
        return
    row = await record_check_in(session, employee, loc, dt.datetime.now(dt.timezone.utc))
    await message.answer(
        t(lang, "checked_in", time=_fmt(row.check_in_at, branch_tz(employee)),
          status=status_label(lang, row.status)),
        reply_markup=main_menu(lang, employee.is_admin),
    )


@router.message(Punch.waiting_location_out, F.location)
async def do_check_out(message, state: FSMContext, employee, lang, session, **_):
    b = employee.branch
    loc = validate_location(
        message, b.latitude, b.longitude, b.radius_m,
        strictness=settings.location_strictness,
        max_age_seconds=settings.location_max_age_seconds,
    )
    await state.clear()
    if not loc.ok:
        await _reject(message, lang, loc, employee)
        return
    row = await record_check_out(session, employee, loc, dt.datetime.now(dt.timezone.utc))
    worked = f"{row.worked_minutes // 60}h {row.worked_minutes % 60}m"
    await message.answer(
        t(lang, "checked_out", time=_fmt(row.check_out_at, branch_tz(employee)), worked=worked),
        reply_markup=main_menu(lang, employee.is_admin),
    )


@router.message(Punch.waiting_location_in)
@router.message(Punch.waiting_location_out)
async def punch_fallback(message: Message, state: FSMContext, employee, lang, **_):
    is_admin = bool(employee and employee.is_admin)
    if message.text and message.text in texts("btn_cancel"):
        await state.clear()
        await message.answer(t(lang, "cancelled"), reply_markup=main_menu(lang, is_admin))
        return
    await message.answer(t(lang, "loc_none"))
