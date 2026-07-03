from aiogram import Router

from app.bot.handlers import admin, attendance, profile, start


def build_router() -> Router:
    router = Router()
    # start eng oxirida — chunki uning fallback handlerlari bor emas; lekin
    # onboarding state boshqalardan oldin tekshirilishi shart emas.
    router.include_router(start.router)
    router.include_router(admin.router)
    router.include_router(attendance.router)
    router.include_router(profile.router)
    return router
