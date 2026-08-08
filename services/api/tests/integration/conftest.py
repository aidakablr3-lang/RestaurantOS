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

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from alembic import command

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# Must happen at conftest import time, not inside a fixture. pytest loads
# every conftest.py in this subtree before it *collects* (imports) any
# test module here -- and several of those modules (e.g. test_auth_router.py)
# import restaurant_os_api.main, whose module-level `app = create_app()`
# calls the @lru_cache'd get_settings() as a side effect of that import.
# If that first call happens before DATABASE_URL is set to
# TEST_DATABASE_URL, the cached Settings permanently carries the
# production-default database URL (localhost:5432) for the rest of the
# test process, regardless of what _run_alembic_upgrade() sets afterward.
if TEST_DATABASE_URL is not None:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

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


# The role migrations run as (whatever TEST_DATABASE_URL names) owns every
# table it creates, and Postgres always lets a table's owner bypass Row-
# Level Security -- exactly like it always lets a superuser bypass RLS,
# with no override for either case (FORCE ROW LEVEL SECURITY changes the
# owner case, but the migrations don't set it, and nothing changes the
# superuser case regardless). Data Architecture v2.0 SS4.1's RLS
# guarantee is therefore untestable through the same role that ran the
# migration -- a real regression could silently ship with RLS policies
# that exist but don't actually apply to anyone, and this suite would
# still pass. This role is a plain, unprivileged, non-owner login used
# only for running queries in tests, so RLS is enforced exactly as it
# would be for the real API's own runtime connection.
_APP_ROLE = "restaurantos_rls_test"
_APP_ROLE_PASSWORD = "restaurantos_rls_test"  # nosec: disposable local/CI test role only


def _provision_unprivileged_app_role(admin_database_url: str) -> None:
    async def _run() -> None:
        url = make_url(admin_database_url)
        conn = await asyncpg.connect(
            user=url.username,
            password=url.password,
            host=url.host,
            port=url.port,
            database=url.database,
        )
        try:
            role_exists = await conn.fetchval(
                "SELECT 1 FROM pg_roles WHERE rolname = $1", _APP_ROLE
            )
            if not role_exists:
                await conn.execute(f"CREATE ROLE {_APP_ROLE} LOGIN PASSWORD '{_APP_ROLE_PASSWORD}'")
            # Re-granted every session (idempotent) since alembic's
            # downgrade/upgrade cycle drops and recreates every table.
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {_APP_ROLE}")
            await conn.execute(
                f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {_APP_ROLE}"
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _as_app_role_url(admin_database_url: str) -> str:
    return (
        make_url(admin_database_url)
        .set(username=_APP_ROLE, password=_APP_ROLE_PASSWORD)
        .render_as_string(hide_password=False)
    )


@pytest.fixture(scope="session")
def engine() -> Generator[AsyncEngine]:
    """Session-scoped and deliberately a plain (non-async) fixture.

    ``create_async_engine`` does no I/O itself — it just builds the engine
    object, lazily — so nothing here actually needs an event loop. Making
    this fixture async (as it originally was) required calling
    ``_run_alembic_upgrade()``'s own ``asyncio.run()`` (inside alembic's
    ``env.py``) from a coroutine already running inside pytest-asyncio's
    event loop, which PostgreSQL/Python correctly reject: "asyncio.run()
    cannot be called from a running event loop." A plain sync fixture runs
    with no event loop active at all, so ``asyncio.run()`` here is exactly
    the ordinary top-level case it's designed for.

    ``poolclass=NullPool``: some integration tests (``test_auth_router.py``)
    drive the app through Starlette's ``TestClient``, which runs the ASGI
    app on its own internal event loop/thread, distinct from the one
    pytest-asyncio hands to this session's async fixtures and test
    functions. A normal pool hands out whatever idle connection is
    available regardless of which loop it was created on; on Windows this
    crashes ("attached to a different loop") the moment a pooled
    connection is reused from a different loop than the one that opened
    it. ``NullPool`` never reuses a connection across checkouts, so each
    one is always opened fresh on whichever loop is asking for it.
    """
    _run_alembic_upgrade()
    _provision_unprivileged_app_role(TEST_DATABASE_URL)  # type: ignore[arg-type]
    app_role_url = _as_app_role_url(TEST_DATABASE_URL)  # type: ignore[arg-type]
    eng = create_async_engine(app_role_url, poolclass=NullPool)
    yield eng
    asyncio.run(eng.dispose())
    _run_alembic_downgrade()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(engine: AsyncEngine) -> AsyncGenerator[None]:
    """Truncate every table between tests so they don't leak state.

    Uses a superuser-equivalent connection deliberately so RLS never
    blocks the cleanup itself — the tests being cleaned up between are
    the ones actually exercising RLS. Covers every table Sprint 4.1
    (Tenant Platform) added, not just the Sprint 3 identity/auth set --
    this fixture predates those tables and was never extended for them.
    """
    yield
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE TABLE outbox_events, user_roles, role_permissions, roles, "
            "tenant_directory_entries, feature_flags, system_settings, subscriptions, "
            "sessions, users, tenants RESTART IDENTITY CASCADE"
        )
        # `permissions` is deliberately excluded: it's fixed platform
        # reference data seeded once by the 0003 migration (RBAC
        # Foundation Architecture SS4.2, "same as currencies"), not
        # per-test data -- truncating it would break every RBAC test
        # after the first, since role_permissions.permission_code is an
        # ON DELETE RESTRICT foreign key into it.
