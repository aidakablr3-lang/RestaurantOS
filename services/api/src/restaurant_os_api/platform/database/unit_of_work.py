"""Unit of Work — one database transaction per use case.

Technical Architecture v2.0 SS6.4: a use case never opens its own
transaction directly. It receives a ``UnitOfWork`` via DI and everything
it does happens inside that single transaction boundary — this is what
makes a future Outbox insert (Technical Architecture v2.0 Group B, not
yet introduced in this PR) atomic with the business write it accompanies.

This is also the **only** place that issues ``SET LOCAL app.tenant_id``
(Data Architecture v2.0 SS4.1/SS4.8) — transaction-scoped, safe under
PgBouncer transaction-mode pooling, because ``SET LOCAL`` resets at
``COMMIT``/``ROLLBACK`` regardless of whether the underlying physical
connection is reused.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.platform.tenancy import TenantContext


class UnitOfWork:
    """Async context manager wrapping exactly one transaction.

    ``tenant_context`` is optional: the login use case runs *before* a
    tenant is authoritatively known from a validated session, so it
    resolves the tenant itself and does not require RLS scoping for the
    lookup-by-email step (that repository method filters by tenant_id
    explicitly at the application layer regardless — Data Architecture
    v2.0 SS4.1's belt-and-suspenders model applies even when only one of
    the two layers is active for a given call).
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_context: TenantContext | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_context = tenant_context
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork used outside of an `async with` block.")
        return self._session

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        if self._tenant_context is not None:
            await self._session.execute(
                text("SET LOCAL app.tenant_id = :tenant_id"),
                {"tenant_id": self._tenant_context.tenant_id},
            )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
