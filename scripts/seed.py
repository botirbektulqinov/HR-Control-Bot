"""Jadvallarni yaratadi + boshlang'ich ma'lumot (filial, jadval, xodimlar).

Ishlatish:  python -m scripts.seed
Har bir xodim JSHSHIR bo'yicha idempotent — qayta ishlatilса dublikat qo'shmaydi.
Prod'da Alembic migratsiyalaridan foydalaning; bu qulay dev boshlanishi.
"""

import asyncio
import datetime as dt

from sqlalchemy import select

import app.db.models  # noqa: F401 (modellarni ro'yxatga olish uchun)
from app.db.base import Base, Session, engine
from app.db.models import Branch, Employee, WorkSchedule

# Marketing bo'limi — sinov xodimlari (F.I.Sh, JSHSHIR)
MARKETING = [
    ("Bafoyeva Nargiza Jahongir qizi", "62706055360039"),
    ("Toshpo'latov Shohruh Dilshod o'g'li", "52612056620027"),
    ("Orifjonova Jamila Murod qizi", "62505076520056"),
    ("Hamidova Gulshirin Azamat qizi", "60412056210018"),
    ("Sabirova Sarvinoz Jonibek qizi", "60507037170024"),
    ("Botirbek To'lqinov Xolmat o'g'li", "52701066040016"),
    ("Jabborqulov Otabek Ulug'bek o'g'li", "51506066390014"),
    ("Sadullayeva Farizabonu Utkirovna", "63110075260014"),
]


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as s:
        branch = await s.scalar(select(Branch))
        if branch is None:
            # Ofis: Ustoz AI, Navoiy shoh ko'chasi 11 (Toshkent).
            branch = Branch(
                name="Bosh ofis (Toshkent)",
                latitude=41.320589, longitude=69.262289,
                radius_m=200, timezone="Asia/Tashkent",
            )
            s.add(branch)

        schedule = await s.scalar(select(WorkSchedule))
        if schedule is None:
            schedule = WorkSchedule(
                name="10:00–19:00", start_time=dt.time(10, 0), end_time=dt.time(19, 0),
                grace_minutes=5, workdays="1,2,3,4,5,6",  # Dush–Shan (Yakshanba dam)
            )
            s.add(schedule)
        await s.flush()

        existing = set(
            (await s.scalars(select(Employee.jshshir))).all()
        )
        added = 0
        for full_name, jshshir in MARKETING:
            if jshshir in existing:
                continue
            s.add(Employee(
                jshshir=jshshir, full_name=full_name, department="Marketing",
                branch_id=branch.id, schedule_id=schedule.id,
            ))
            added += 1

        await s.commit()
        print(f"Seed tayyor. Marketing xodimlari qo'shildi: {added} ta.")


if __name__ == "__main__":
    asyncio.run(main())
