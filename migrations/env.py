import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401 (metadata to'lishi uchun)
from app.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata
url = get_settings().database_url


def _configure(connection=None):
    if connection is None:
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    else:
        context.configure(connection=connection, target_metadata=target_metadata)


def run_offline() -> None:
    _configure()
    with context.begin_transaction():
        context.run_migrations()


def _do(connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(_do)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
