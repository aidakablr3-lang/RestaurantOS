"""Fixtures for integration tests requiring a real PostgreSQL instance.

Technical Architecture v2.0 SS9.6: integration tests run against real
Postgres/Redis via CI service containers — not mocked. Locally, these
tests activate only when ``TEST_DATABASE_URL`` is set (e.g., pointed at
a disposable local/CI Postgres 17 instance); otherwise the whole
directory is skipped with a clear reason rather than failing, since a
missing database is an environment-configuration fact, not a test
failure.

Schema setup runs the real Alembic migration (not
``Base.metadata.create_all``) deliberately: the Row-Level Security
policies and triggers this module's security guarantees depend on are
hand-written SQL inside the migration (Data Architecture v2.0 SS4.1),
not expressible as SQLAlchemy declarative model metadata — a
metadata-only test database would silently skip testing RLS at all.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

_SKIP_REASON = (
    "TEST_DATABASE_URL is not set — integration tests require a real "
    "PostgreSQL 17 instance (see Technical Architecture v2.0 SS9.6). "
    "Example: postgresql+asyncpg://restaurantos:restaurantos@localhost:5432/restaurantos_test"
)

pytestmark = pytest.mark.integration

_API_ROOT = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip every test under this directory when no test database is configured.

    Deliberately not a `skipif` marker or a `pytest.skip()` call at
    conftest import time: both were tried and both let a session-scoped
    autouse fixture (`_clean_tables` -> `engine`) attempt setup anyway,
    turning a missing database into a setup ERROR instead of a clean
    SKIP. This hook runs during collection, before any fixture is
    instantiated, which is the one mechanism verified to actually
    prevent that.
    """
    if TEST_DATABASE_URL is not None:
        return
    skip_marker = pytest.mark.skip(reason=_SKIP_REASON)
    for item in items:
        item.add_marker(skip_marker)


def _run_alembic_upgrade() -> None:
    alembic_cfg = Config(str(_API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_API_ROOT / "alembic"))
    # Alembic's own env.py resolves the URL from Settings; TEST_DATABASE_URL
    # is exported as DATABASE_URL for the duration of this call so it picks
    # up the test database instead of the development default.
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # type: ignore[assignment]
    command.upgrade(alembic_cfg, "head")


def _run_alembic_downgrade() -> None:
    alembic_cfg = Config(str(_API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_API_ROOT / "alembic"))
    command.downgrade(alembic_cfg, "base")


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine]:
    _run_alembic_upgrade()
    eng = create_async_engine(TEST_DATABASE_URL)
    yield eng
    await eng.dispose()
    _run_alembic_downgrade()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(engine: AsyncEngine) -> AsyncGenerator[None]:
    """Truncate every table between tests so they don't leak state.

    Uses a superuser-equivalent connection deliberately so RLS never
    blocks the cleanup itself — the tests being cleaned up between are
    the ones actually exercising RLS.
    """
    yield
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE sessions, users, tenants RESTART IDENTITY CASCADE"
        )
