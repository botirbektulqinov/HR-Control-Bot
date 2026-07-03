from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Employee


def is_valid_jshshir(value: str) -> bool:
    v = value.strip()
    return len(v) == 14 and v.isdigit()


async def get_by_telegram(session: AsyncSession, telegram_id: int) -> Employee | None:
    return await session.scalar(
        select(Employee).where(Employee.telegram_id == telegram_id)
    )


async def get_by_jshshir(session: AsyncSession, jshshir: str) -> Employee | None:
    return await session.scalar(
        select(Employee).where(Employee.jshshir == jshshir.strip())
    )


async def link_telegram(
    session: AsyncSession, employee: Employee, telegram_id: int, username: str | None
) -> None:
    employee.telegram_id = telegram_id
    employee.telegram_username = username
    await audit(session, employee.id, "link_telegram", str(telegram_id))


async def audit(
    session: AsyncSession,
    actor_id: int | None,
    action: str,
    target: str | None = None,
    **detail,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target=target,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
    )
