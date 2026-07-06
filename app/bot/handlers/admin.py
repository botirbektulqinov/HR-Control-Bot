import datetime as dt
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message
from sqlalchemy import select

from app.bot.keyboards import admin_menu, main_menu, report_period_kb
from app.bot.states import AdminFlow
from app.config import get_settings
from app.constants import Role
from app.db.models import Branch, Employee, WorkSchedule
from app.i18n import t, texts
from app.services.auth import audit, get_by_jshshir, is_valid_jshshir
from app.services.reports import build_report

router = Router()
settings = get_settings()


def _today() -> dt.date:
    return dt.datetime.now(ZoneInfo(settings.default_timezone)).date()


def _parse_range(text: str) -> tuple[dt.date, dt.date] | None:
    parts = text.split()
    if len(parts) != 2:
        return None
    try:
        a, b = dt.date.fromisoformat(parts[0]), dt.date.fromisoformat(parts[1])
    except ValueError:
        return None
    return (a, b) if a <= b else (b, a)


def _is_admin(employee: Employee | None) -> bool:
    return bool(employee and employee.is_admin)


def _is_super(employee: Employee | None) -> bool:
    return bool(employee and employee.role == Role.SUPER_ADMIN.value)


@router.message(F.text.in_(texts("menu_admin")))
async def admin_open(message: Message, employee, lang, state: FSMContext, **_):
    await state.clear()
    if not _is_admin(employee):
        await message.answer(t(lang, "not_admin"))
        return
    await message.answer(t(lang, "admin_menu"), reply_markup=admin_menu(lang, _is_super(employee)))


@router.message(F.text.in_(texts("admin_reports")))
async def reports_open(message: Message, employee, lang, state: FSMContext, **_):
    if not _is_admin(employee):
        return
    await state.set_state(AdminFlow.report_range)
    await message.answer(t(lang, "report_prompt"), reply_markup=report_period_kb(lang))


@router.message(AdminFlow.report_range)
async def reports_generate(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await state.clear()
        await message.answer(t(lang, "admin_menu"), reply_markup=admin_menu(lang, _is_super(employee)))
        return

    if text in texts("report_today"):
        d_from = d_to = _today()
    elif text in texts("report_month"):
        d_to = _today()
        d_from = d_to.replace(day=1)
    else:
        parsed = _parse_range(text)
        if not parsed:
            await message.answer(t(lang, "report_prompt"))
            return
        d_from, d_to = parsed

    await message.answer(t(lang, "report_generating"))
    result = await build_report(session, d_from, d_to, lang)
    if result is None:
        await message.answer(t(lang, "report_empty"))
        return
    fname, buf = result
    await message.answer_document(BufferedInputFile(buf.read(), filename=fname))
    await state.clear()
    await message.answer(t(lang, "admin_menu"), reply_markup=admin_menu(lang, _is_super(employee)))


@router.message(F.text.in_(texts("admin_reset_link")))
async def reset_open(message: Message, employee, lang, state: FSMContext, **_):
    if not _is_admin(employee):
        return
    await state.set_state(AdminFlow.reset_jshshir)
    await message.answer(t(lang, "reset_prompt"))


@router.message(AdminFlow.reset_jshshir)
async def reset_do(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await state.clear()
        await message.answer(t(lang, "admin_menu"), reply_markup=admin_menu(lang, _is_super(employee)))
        return
    emp = await get_by_jshshir(session, text)
    if emp is None:
        await message.answer(t(lang, "not_found"))
        return
    emp.telegram_id = None
    emp.telegram_username = None
    await audit(session, employee.id, "reset_link", emp.jshshir)
    await state.clear()
    await message.answer(t(lang, "reset_done", name=emp.full_name),
                         reply_markup=admin_menu(lang, _is_super(employee)))


@router.message(F.text.in_(texts("admin_add_hr")))
async def addhr_open(message: Message, employee, lang, state: FSMContext, **_):
    if not _is_super(employee):
        return
    await state.set_state(AdminFlow.addhr_jshshir)
    await message.answer(t(lang, "addhr_prompt"))


@router.message(AdminFlow.addhr_jshshir)
async def addhr_do(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await state.clear()
        await message.answer(t(lang, "admin_menu"), reply_markup=admin_menu(lang, _is_super(employee)))
        return
    emp = await get_by_jshshir(session, text)
    if emp is None:
        await message.answer(t(lang, "not_found"))
        return
    emp.role = Role.HR.value
    await audit(session, employee.id, "add_hr", emp.jshshir)
    await state.clear()
    await message.answer(t(lang, "addhr_done", name=emp.full_name),
                         reply_markup=admin_menu(lang, _is_super(employee)))


async def _to_admin_menu(message: Message, employee, lang, state: FSMContext):
    await state.clear()
    await message.answer(t(lang, "admin_menu"), reply_markup=admin_menu(lang, _is_super(employee)))


@router.message(F.text.in_(texts("admin_add_employee")))
async def addemp_open(message: Message, employee, lang, state: FSMContext, **_):
    if not _is_admin(employee):
        return
    await state.set_state(AdminFlow.add_emp_name)
    await message.answer(t(lang, "addemp_name"))


@router.message(AdminFlow.add_emp_name)
async def addemp_name(message: Message, employee, lang, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await _to_admin_menu(message, employee, lang, state)
        return
    await state.update_data(name=text)
    await state.set_state(AdminFlow.add_emp_jshshir)
    await message.answer(t(lang, "addemp_jshshir"))


@router.message(AdminFlow.add_emp_jshshir)
async def addemp_jshshir(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await _to_admin_menu(message, employee, lang, state)
        return
    if not is_valid_jshshir(text):
        await message.answer(t(lang, "invalid_jshshir"))
        return
    if await get_by_jshshir(session, text):
        await message.answer(t(lang, "addemp_exists"))
        return
    await state.update_data(jshshir=text)
    await state.set_state(AdminFlow.add_emp_dept)
    await message.answer(t(lang, "addemp_dept"))


@router.message(AdminFlow.add_emp_dept)
async def addemp_dept(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await _to_admin_menu(message, employee, lang, state)
        return
    branch = await session.scalar(select(Branch))
    schedule = await session.scalar(select(WorkSchedule))
    if branch is None or schedule is None:
        await state.clear()
        await message.answer(t(lang, "addemp_no_config"),
                             reply_markup=admin_menu(lang, _is_super(employee)))
        return
    data = await state.get_data()
    session.add(Employee(
        jshshir=data["jshshir"], full_name=data["name"],
        department=None if text == "-" else text,
        branch_id=branch.id, schedule_id=schedule.id,
    ))
    await audit(session, employee.id, "add_employee", data["jshshir"])
    await state.clear()
    await message.answer(t(lang, "addemp_done", name=data["name"]),
                         reply_markup=admin_menu(lang, _is_super(employee)))


@router.message(F.text.in_(texts("back")))
async def back_to_main(message: Message, employee, lang, state: FSMContext, **_):
    await state.clear()
    await message.answer(t(lang, "welcome_back", name=employee.full_name if employee else ""),
                         reply_markup=main_menu(lang, _is_admin(employee)))
