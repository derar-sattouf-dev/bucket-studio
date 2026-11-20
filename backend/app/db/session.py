"""Database engine and session factory (SQLite via aiosqlite)."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Resolve relative to the backend root, never the cwd.
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_DIR = Path(settings.data_dir) if settings.data_dir else _BASE_DIR / "data"
DB_PATH = DB_DIR / "images.db"

DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
SYNC_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
    """Per-connection pragmas (they are not persisted in the DB file, except journal_mode)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def init_db() -> None:
    """Bring the schema up to date (Alembic). Runs in a thread: Alembic is synchronous."""
    from app.db.migrate import run_migrations

    await asyncio.to_thread(run_migrations)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
