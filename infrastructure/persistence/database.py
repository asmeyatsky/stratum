"""
Async database engine and session management for Stratum.

Architectural Intent:
    Provides a SQLAlchemy 2.0 async engine backed by aiosqlite for local
    development and testing. The DATABASE_URL is configurable via environment
    variable so that production deployments can swap in PostgreSQL or another
    async-compatible backend without touching application code.

    - ``init_db()`` creates all tables declared via the shared ``Base``
      metadata.  Called once during application lifespan startup.
    - ``get_db_session()`` is an async generator suitable for FastAPI's
      ``Depends()`` mechanism — it yields a session and ensures cleanup.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./stratum.db",
)

engine = create_async_engine(DATABASE_URL, echo=False)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


async def init_db() -> None:
    """Create all tables defined in Base.metadata.

    Safe to call multiple times — SQLAlchemy's ``create_all`` is a no-op
    for tables that already exist.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` scoped to a single request.

    The session is automatically closed when the request handler completes,
    regardless of whether the handler succeeded or raised an exception.
    """
    async with async_session_factory() as session:
        yield session
