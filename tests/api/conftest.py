"""Shared fixtures for API integration tests."""

import os

# Set a very high rate limit before the middleware module is imported.
# The RateLimitMiddleware reads these at import time.
os.environ["RATE_LIMIT_RPM"] = "100000"
os.environ["RATE_LIMIT_BURST"] = "10000"

import pytest  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.config.dependency_injection import Container  # noqa: E402
from infrastructure.persistence.database import Base, get_db_session  # noqa: E402
from presentation.api.app import app  # noqa: E402


# ---------------------------------------------------------------------------
# In-memory SQLite engine for fast, isolated tests
# ---------------------------------------------------------------------------

_test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_test_session_factory = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def _override_get_db_session():
    """Yield a test-scoped async session backed by in-memory SQLite."""
    async with _test_session_factory() as session:
        yield session


# Override the database dependency for the entire test suite
app.dependency_overrides[get_db_session] = _override_get_db_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _setup_test_db():
    """Create all tables before each test and drop them after.

    This ensures every test starts with a clean database.
    """
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints.

    Sets ``app.state.container`` so that endpoints depending on the DI
    Container (e.g. trigger_analysis) do not return 503.
    """
    app.state.container = Container.create()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """Headers for dev-mode auth (no STRATUM_API_KEY set)."""
    return {}
