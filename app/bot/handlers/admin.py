import datetime as dt
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import delete, select, update

from app.bot.keyboards import (
    admin_menu,
    delete_confirm_kb,
    edit_fields_kb,
    main_menu,
    report_period_kb,
)
from app.bot.states import AdminFlow
from app.config import get_settings
from app.constants import Role
from app.db.models import Attendance, AuditLog, Branch, Employee, WorkSchedule
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


_EDIT_FIELDS = {"name": "full_name", "dept": "department", "pos": "position"}


def _edit_card(lang: str, emp: Employee) -> str:
    return t(lang, "edit_card", name=emp.full_name,
             dept=emp.department or "—", position=emp.position or "—")


@router.message(F.text.in_(texts("admin_edit_employee")))
async def edit_open(message: Message, employee, lang, state: FSMContext, **_):
    if not _is_admin(employee):
        return
    await state.set_state(AdminFlow.edit_find)
    await message.answer(t(lang, "edit_find"))


@router.message(AdminFlow.edit_find)
async def edit_find(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await _to_admin_menu(message, employee, lang, state)
        return
    emp = await get_by_jshshir(session, text)
    if emp is None:
        await message.answer(t(lang, "not_found"))
        return
    await state.update_data(edit_emp_id=emp.id)
    await state.set_state(AdminFlow.edit_menu)
    await message.answer(_edit_card(lang, emp), reply_markup=edit_fields_kb(lang))


@router.callback_query(F.data.startswith("editf:"))
async def edit_pick_field(cb: CallbackQuery, lang, state: FSMContext, **_):
    data = await state.get_data()
    if not data.get("edit_emp_id"):
        await cb.answer(t(lang, "edit_expired"), show_alert=True)
        return
    await state.update_data(edit_field=cb.data.split(":", 1)[1])
    await state.set_state(AdminFlow.edit_value)
    await cb.message.answer(t(lang, "edit_ask_value"))
    await cb.answer()


@router.callback_query(F.data == "editdone")
async def edit_done(cb: CallbackQuery, employee, lang, state: FSMContext, **_):
    await state.clear()
    await cb.message.answer(t(lang, "admin_menu"),
                            reply_markup=admin_menu(lang, _is_super(employee)))
    await cb.answer()


@router.message(AdminFlow.edit_value)
async def edit_value(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await _to_admin_menu(message, employee, lang, state)
        return
    data = await state.get_data()
    emp = await session.get(Employee, data.get("edit_emp_id"))
    field = _EDIT_FIELDS.get(data.get("edit_field"))
    if emp is None or field is None:
        await state.clear()
        await message.answer(t(lang, "edit_expired"),
                             reply_markup=admin_menu(lang, _is_super(employee)))
        return
    if field == "full_name":
        if not text or text == "-":
            await message.answer(t(lang, "edit_ask_value"))
            return
        value = text
    else:
        value = None if text == "-" else text
    setattr(emp, field, value)
    await audit(session, employee.id, "edit_employee", emp.jshshir, field=field)
    await state.set_state(AdminFlow.edit_menu)
    await message.answer(t(lang, "edit_saved"))
    await message.answer(_edit_card(lang, emp), reply_markup=edit_fields_kb(lang))


@router.message(F.text.in_(texts("admin_delete_employee")))
async def delete_open(message: Message, employee, lang, state: FSMContext, **_):
    if not _is_admin(employee):
        return
    await state.set_state(AdminFlow.delete_find)
    await message.answer(t(lang, "del_find"))


@router.message(AdminFlow.delete_find)
async def delete_find(message: Message, employee, lang, session, state: FSMContext, **_):
    text = (message.text or "").strip()
    if text in texts("back"):
        await _to_admin_menu(message, employee, lang, state)
        return
    emp = await get_by_jshshir(session, text)
    if emp is None:
        await message.answer(t(lang, "not_found"))
        return
    if emp.id == employee.id:
        await message.answer(t(lang, "del_self"))
        return
    await state.update_data(del_emp_id=emp.id)
    await state.set_state(AdminFlow.delete_confirm)
    await message.answer(t(lang, "del_confirm", name=emp.full_name, jshshir=emp.jshshir),
                         reply_markup=delete_confirm_kb(lang))


@router.callback_query(F.data == "delyes")
async def delete_yes(cb: CallbackQuery, employee, lang, session, state: FSMContext, **_):
    data = await state.get_data()
    emp = await session.get(Employee, data.get("del_emp_id"))
    if emp is None:
        await state.clear()
        await cb.message.answer(t(lang, "edit_expired"),
                                reply_markup=admin_menu(lang, _is_super(employee)))
        await cb.answer()
        return
    name, jshshir = emp.full_name, emp.jshshir
    # FK: avval davomat va audit-aktor havolalarini tozalaymiz
    await session.execute(delete(Attendance).where(Attendance.employee_id == emp.id))
    await session.execute(
        update(AuditLog).where(AuditLog.actor_id == emp.id).values(actor_id=None)
    )
    await session.delete(emp)
    await audit(session, employee.id, "delete_employee", jshshir)
    await state.clear()
    await cb.message.answer(t(lang, "del_done", name=name),
                            reply_markup=admin_menu(lang, _is_super(employee)))
    await cb.answer()


@router.callback_query(F.data == "delno")
async def delete_no(cb: CallbackQuery, employee, lang, state: FSMContext, **_):
    await state.clear()
    await cb.message.answer(t(lang, "cancelled"),
                            reply_markup=admin_menu(lang, _is_super(employee)))
    await cb.answer()


@router.message(F.text.in_(texts("back")))
async def back_to_main(message: Message, employee, lang, state: FSMContext, **_):
    await state.clear()
    await message.answer(t(lang, "welcome_back", name=employee.full_name if employee else ""),
                         reply_markup=main_menu(lang, _is_admin(employee)))
