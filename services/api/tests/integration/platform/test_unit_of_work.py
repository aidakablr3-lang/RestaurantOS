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

    async def test_tenant_context_does_not_leak_into_a_later_transaction(
        self, session_factory
    ) -> None:
        """``set_config(..., true)`` (``is_local``) must reset at COMMIT,
        the same guarantee ``SET LOCAL`` gave -- otherwise a pooled
        connection could leak one request's tenant scope into the next."""
        tenant_id = generate_ulid()

        async with UnitOfWork(session_factory, TenantContext(tenant_id)):
            pass

        async with UnitOfWork(session_factory) as uow:
            result = await uow.session.execute(
                text("SELECT current_setting('app.tenant_id', true)")
            )
            assert result.scalar_one() == ""
