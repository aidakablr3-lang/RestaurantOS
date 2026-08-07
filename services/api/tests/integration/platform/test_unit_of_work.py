"""Integration tests for ``UnitOfWork``'s transaction-local tenant context.

Requires TEST_DATABASE_URL (see tests/integration/conftest.py).

Regression coverage for a defect found during Sprint 4.1 Step 3 manual
browser verification against a real PostgreSQL database:
``UnitOfWork.__aenter__`` originally issued
``SET LOCAL app.tenant_id = :tenant_id`` as a bound parameter. PostgreSQL's
``SET``/``SET LOCAL`` statement does not accept a bind parameter -- the
value must be a literal -- so asyncpg rejected it with
``PostgresSyntaxError: syntax error at or near "$1"`` on every
tenant-scoped ``UnitOfWork``, in every module. This was never caught
before because this module's own verification ran against in-memory
fakes, never a live PostgreSQL instance (see docs/AI_HANDOFF.md). The
fix uses ``SELECT set_config('app.tenant_id', :tenant_id, true)``
instead, an ordinary function call that accepts bind parameters and has
identical transaction-local (``is_local=true``) reset-at-commit
semantics.
"""

from __future__ import annotations

from sqlalchemy import text

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class TestUnitOfWorkTenantContext:
    async def test_entering_with_a_tenant_context_sets_app_tenant_id(self, session_factory) -> None:
        """Reproduces the original failure: this raised
        ``asyncpg.exceptions.PostgresSyntaxError`` on ``__aenter__`` before
        the fix, for every tenant-scoped ``UnitOfWork`` -- not specific to
        any particular query afterward."""
        tenant_id = generate_ulid()

        async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
            result = await uow.session.execute(
                text("SELECT current_setting('app.tenant_id', true)")
            )
            assert result.scalar_one() == tenant_id

    async def test_tenant_context_does_not_leak_into_a_later_transaction_on_the_same_connection(
        self, engine
    ) -> None:
        """``set_config(..., true)`` (``is_local``) must reset at COMMIT,
        the same guarantee ``SET LOCAL`` gave -- otherwise a single
        physical connection, reused by a later request under normal
        pooling, could see a stale ``tenant_id`` left over from whatever
        request used that connection last.

        Uses one connection directly (not through ``session_factory``,
        which sits on a ``NullPool`` for this test session specifically
        so ``TestClient``-driven tests never reuse a connection across
        event loops -- see conftest.py) so physical-connection reuse is
        forced and deterministic here, not incidental.
        """
        tenant_id = generate_ulid()

        async with engine.connect() as conn:
            async with conn.begin():
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": tenant_id},
                )
            async with conn.begin():
                result = await conn.execute(text("SELECT current_setting('app.tenant_id', true)"))
                assert result.scalar_one() == ""
