"""IdempotencyGuard -- the single reusable Application-layer wrapper
Technical Architecture v2.0 Group B specifies: "checks a tenant-scoped
idempotency record (key, request hash, result, expiry) before executing
any use case."

Concurrency-safety mechanism (Step 4 Decision Lock, Decision 1):
**insert-a-placeholder-row-before-executing**, not execute-then-record.
``_try_claim`` inserts a row with ``response_status IS NULL`` in its own
short transaction; a concurrent duplicate request's own insert hits the
``UNIQUE(tenant_id, idempotency_key)`` constraint immediately and gets
``IdempotentRequestInProgressError`` (409) rather than blocking or
racing the first request's own use case execution. This is
deliberately non-blocking: a concurrent duplicate does not wait for the
in-flight request to finish, it is told to retry -- simpler and more
predictable than holding a transaction open for however long the
wrapped use case takes, and correct because the underlying use case is
guaranteed to run at most once per key regardless.

Only known, already-shaped ``(status, body)`` outcomes are cached and
replayed -- an exception raised out of ``execute`` is treated as
unexpected (never cached), releases the claim so a retry gets a fresh
attempt, and re-raises unchanged. Callers are expected to catch their
own module's domain exceptions and shape them into ``(status, body)``
*inside* the ``execute`` callable (see
``core/exceptions.py::build_error_response``) so an expected 4xx is
cached and replayed exactly like a 2xx would be -- a retry with the
same key and body always gets the same answer, success or failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.idempotency.exceptions import (
    IdempotencyKeyConflictError,
    IdempotentRequestInProgressError,
)
from restaurant_os_api.platform.idempotency.models import IdempotencyKeyModel
from restaurant_os_api.platform.tenancy import TenantContext

_DEFAULT_TTL = timedelta(hours=24)


class IdempotencyGuard:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ttl: timedelta = _DEFAULT_TTL,
    ) -> None:
        self._session_factory = session_factory
        self._ttl = ttl

    async def run(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        execute: Callable[[], Awaitable[tuple[int, dict[str, Any]]]],
    ) -> tuple[int, dict[str, Any]]:
        claimed = await self._try_claim(tenant_id, idempotency_key, request_fingerprint)
        if not claimed:
            return await self._resolve_existing(tenant_id, idempotency_key, request_fingerprint)

        try:
            status, body = await execute()
        except Exception:
            await self._release_claim(tenant_id, idempotency_key)
            raise

        await self._record_response(tenant_id, idempotency_key, status, body)
        return status, body

    async def _try_claim(
        self, tenant_id: str, idempotency_key: str, request_fingerprint: str
    ) -> bool:
        try:
            async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
                uow.session.add(
                    IdempotencyKeyModel(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        idempotency_key=idempotency_key,
                        request_fingerprint=request_fingerprint,
                        expires_at=datetime.now(UTC) + self._ttl,
                    )
                )
            return True
        except IntegrityError:
            return False

    async def _resolve_existing(
        self, tenant_id: str, idempotency_key: str, request_fingerprint: str
    ) -> tuple[int, dict[str, Any]]:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            stmt = select(IdempotencyKeyModel).where(
                IdempotencyKeyModel.tenant_id == tenant_id,
                IdempotencyKeyModel.idempotency_key == idempotency_key,
            )
            existing = (await uow.session.execute(stmt)).scalar_one_or_none()

        if existing is None:
            # The claim we just failed to take existed a moment ago but
            # is gone now (e.g. a rare cleanup-job race) -- tell the
            # caller to retry rather than silently re-claiming, keeping
            # this method's contract simple: a conflict here always
            # means "ask again."
            raise IdempotentRequestInProgressError(idempotency_key)
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyKeyConflictError(idempotency_key)
        if existing.response_status is None:
            raise IdempotentRequestInProgressError(idempotency_key)
        return existing.response_status, existing.response_body or {}

    async def _record_response(
        self, tenant_id: str, idempotency_key: str, status: int, body: dict[str, Any]
    ) -> None:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            await uow.session.execute(
                update(IdempotencyKeyModel)
                .where(
                    IdempotencyKeyModel.tenant_id == tenant_id,
                    IdempotencyKeyModel.idempotency_key == idempotency_key,
                )
                .values(response_status=status, response_body=body)
            )

    async def _release_claim(self, tenant_id: str, idempotency_key: str) -> None:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            await uow.session.execute(
                delete(IdempotencyKeyModel).where(
                    IdempotencyKeyModel.tenant_id == tenant_id,
                    IdempotencyKeyModel.idempotency_key == idempotency_key,
                )
            )
