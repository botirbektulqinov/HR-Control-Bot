from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from app.db.base import Session
from app.services.auth import get_by_telegram


class DbSessionMiddleware(BaseMiddleware):
    """Har bir update uchun bitta session; muvaffaqiyatda commit, xatoda rollback."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with Session() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class AuthMiddleware(BaseMiddleware):
    """telegram_id bo'yicha xodimni yuklaydi -> data['employee'], data['lang']."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data["session"]
        user: User | None = data.get("event_from_user")
        employee = await get_by_telegram(session, user.id) if user else None
        data["employee"] = employee
        data["lang"] = employee.language if employee else "uz"
        return await handler(event, data)
