from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.i18n import LANGUAGES, t


def main_menu(lang: str, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "menu_check_in")),
         KeyboardButton(text=t(lang, "menu_check_out"))],
        [KeyboardButton(text=t(lang, "menu_profile")),
         KeyboardButton(text=t(lang, "menu_history"))],
        [KeyboardButton(text=t(lang, "menu_language"))],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=t(lang, "menu_admin"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def location_kb(lang: str) -> ReplyKeyboardMarkup:
    # Telegram botlari LIVE joylashuvni tugma orqali so'ray olmaydi — foydalanuvchi
    # uni 📎 (biriktirish) → Joylashuv → «Jonli joylashuvni ulashish» orqali beradi.
    # Static joylashuv (request_location) qo'lda tanlangan pin'dan farqlanmaydi, shu
    # sabab uni ishlatmaymiz — faqat Bekor tugmasi.
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_cancel"))]],
        resize_keyboard=True,
    )


def language_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"setlang:{code}")]
            for code, label in LANGUAGES.items()
        ]
    )


def admin_menu(lang: str, is_super: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t(lang, "admin_reports"))],
        [KeyboardButton(text=t(lang, "admin_add_employee")),
         KeyboardButton(text=t(lang, "admin_edit_employee"))],
        [KeyboardButton(text=t(lang, "admin_delete_employee"))],
        [KeyboardButton(text=t(lang, "admin_reset_link"))],
    ]
    if is_super:
        rows.append([KeyboardButton(text=t(lang, "admin_add_hr"))])
    rows.append([KeyboardButton(text=t(lang, "back"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def edit_fields_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "edit_btn_name"), callback_data="editf:name"),
         InlineKeyboardButton(text=t(lang, "edit_btn_dept"), callback_data="editf:dept")],
        [InlineKeyboardButton(text=t(lang, "edit_btn_pos"), callback_data="editf:pos")],
        [InlineKeyboardButton(text=t(lang, "edit_btn_done"), callback_data="editdone")],
    ])


def delete_confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "del_btn_yes"), callback_data="delyes"),
        InlineKeyboardButton(text=t(lang, "del_btn_no"), callback_data="delno"),
    ]])


def report_period_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "report_today")),
             KeyboardButton(text=t(lang, "report_month"))],
            [KeyboardButton(text=t(lang, "back"))],
        ],
        resize_keyboard=True,
    )
