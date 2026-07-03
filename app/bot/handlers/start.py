from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import language_inline, main_menu
from app.bot.states import Onboarding
from app.db.models import Employee
from app.i18n import t
from app.services.auth import get_by_jshshir, is_valid_jshshir, link_telegram

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, employee: Employee | None, lang: str, **_
):
    # Har safar tilni ko'rsatamiz; tanlangach xabar o'chiriladi (set_language).
    await state.clear()
    await message.answer(t(lang, "choose_language"), reply_markup=language_inline())


@router.callback_query(F.data.startswith("setlang:"))
async def set_language(
    cb: CallbackQuery, state: FSMContext, employee: Employee | None, **_
):
    code = cb.data.split(":", 1)[1]
    with suppress(TelegramBadRequest):  # «Tilni tanlang» xabarini o'chirish
        await cb.message.delete()

    if employee:  # allaqachon kirgan foydalanuvchi -> menyu
        employee.language = code
        await cb.message.answer(
            t(code, "welcome_back", name=employee.full_name),
            reply_markup=main_menu(code, employee.is_admin),
        )
    else:  # onboarding: til tanlandi -> JSHSHIR so'raymiz
        await state.update_data(lang=code)
        await state.set_state(Onboarding.waiting_jshshir)
        await cb.message.answer(t(code, "ask_jshshir"))
    await cb.answer()


@router.message(Onboarding.waiting_jshshir, F.text)
async def onboard_jshshir(message: Message, state: FSMContext, session, **_):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    value = message.text.strip()

    if not is_valid_jshshir(value):
        await message.answer(t(lang, "invalid_jshshir"))
        return

    emp = await get_by_jshshir(session, value)
    if emp is None:
        await message.answer(t(lang, "not_found"))
        return
    if emp.telegram_id is not None and emp.telegram_id != message.from_user.id:
        await message.answer(t(lang, "already_linked"))
        return

    await link_telegram(session, emp, message.from_user.id, message.from_user.username)
    emp.language = lang
    await state.clear()
    await message.answer(
        t(lang, "linked_success", name=emp.full_name),
        reply_markup=main_menu(lang, emp.is_admin),
    )
