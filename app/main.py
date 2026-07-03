import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import build_router
from app.bot.middlewares import AuthMiddleware, DbSessionMiddleware
from app.config import get_settings
from app.constants import Role
from app.db.base import Session
from app.db.models import Employee
from app.services.auth import get_by_telegram

settings = get_settings()


async def ensure_super_admins() -> None:
    """.env dagi SUPER_ADMIN_IDS uchun super-admin yozuvini kafolatlaydi."""
    async with Session() as session:
        for tid in settings.super_admin_id_set:
            emp = await get_by_telegram(session, tid)
            if emp is None:
                session.add(Employee(
                    jshshir=f"SA{tid}"[:14], full_name="Super Admin",
                    telegram_id=tid, role=Role.SUPER_ADMIN.value,
                ))
            elif emp.role != Role.SUPER_ADMIN.value:
                emp.role = Role.SUPER_ADMIN.value
        await session.commit()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await ensure_super_admins()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # DbSession tashqarida (Auth sessiyaga muhtoj) -> avval ro'yxatga olinadi
    db_mw, auth_mw = DbSessionMiddleware(), AuthMiddleware()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(db_mw)
        observer.middleware(auth_mw)

    dp.include_router(build_router())

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("HR Control bot ishga tushdi")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
