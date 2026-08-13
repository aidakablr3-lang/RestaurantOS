"""Integration tests for IdempotencyGuard against real PostgreSQL.

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Covers
Step 4 Decision Lock, Decision 1's own requirements directly: replay on
a matching retry, a dedicated conflict on a reused key with a different
body, and that a concurrent duplicate cannot execute the underlying use
case twice (proven here by claiming the placeholder row directly,
simulating the in-flight window a second real concurrent request would
observe, rather than relying on real thread/process concurrency, which
would be flaky under a test runner).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.idempotency import (
    IdempotencyGuard,
    IdempotencyKeyConflictError,
    IdempotentRequestInProgressError,
    fingerprint_request,
)
from restaurant_os_api.platform.tenancy import TenantContext


async def _seed_tenant(session_factory, tenant_id: str) -> None:
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        await uow.session.execute(
            text(
                "INSERT INTO tenants (id, legal_name, display_name, tenant_tier, status, "
                "default_currency_code) VALUES (:id, 'Seed', 'Seed', 'shared', 'active', 'USD')"
            ),
            {"id": tenant_id},
        )


class TestIdempotencyGuard:
    async def test_a_fresh_key_executes_the_use_case_and_returns_its_result(
        self, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        await _seed_tenant(session_factory, tenant_id)
        guard = IdempotencyGuard(session_factory)
        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"created": True}

        status, body = await guard.run(
            tenant_id=tenant_id,
            idempotency_key=generate_ulid(),
            request_fingerprint=fingerprint_request({"a": 1}),
            execute=execute,
        )

        assert status == 201
        assert body == {"created": True}
        assert calls == 1

    async def test_the_same_key_and_body_replays_without_re_executing(
        self, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        await _seed_tenant(session_factory, tenant_id)
        guard = IdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})
        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"created": True, "call": calls}

        first = await guard.run(
            tenant_id=tenant_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=execute,
        )
        second = await guard.run(
            tenant_id=tenant_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=execute,
        )

        assert first == second
        assert calls == 1, "the use case must not run twice for a replayed request"

    async def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        await _seed_tenant(session_factory, tenant_id)
        guard = IdempotencyGuard(session_factory)
        key = generate_ulid()

        async def execute() -> tuple[int, dict]:
            return 201, {"created": True}

        await guard.run(
            tenant_id=tenant_id,
            idempotency_key=key,
            request_fingerprint=fingerprint_request({"a": 1}),
            execute=execute,
        )

        with pytest.raises(IdempotencyKeyConflictError):
            await guard.run(
                tenant_id=tenant_id,
                idempotency_key=key,
                request_fingerprint=fingerprint_request({"a": 2}),
                execute=execute,
            )

    async def test_a_concurrent_duplicate_cannot_execute_the_use_case_twice(
        self, session_factory
    ) -> None:
        """Simulates the exact window a real concurrent second request
        would observe: the placeholder row exists (claimed) but no
        response has been recorded yet. A second ``run()`` call against
        that same key must be rejected, never execute its own callable."""
        tenant_id = generate_ulid()
        await _seed_tenant(session_factory, tenant_id)
        guard = IdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})

        claimed = await guard._try_claim(tenant_id, key, fingerprint)
        assert claimed is True

        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"created": True}

        with pytest.raises(IdempotentRequestInProgressError):
            await guard.run(
                tenant_id=tenant_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                execute=execute,
            )
        assert calls == 0, "a request already in flight must never run a second execution"

    async def test_an_unexpected_exception_releases_the_claim_for_a_fresh_retry(
        self, session_factory
    ) -> None:
        tenant_id = generate_ulid()
        await _seed_tenant(session_factory, tenant_id)
        guard = IdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})
        attempts = 0

        async def failing_then_succeeding() -> tuple[int, dict]:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("transient failure")
            return 201, {"created": True}

        with pytest.raises(RuntimeError):
            await guard.run(
                tenant_id=tenant_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                execute=failing_then_succeeding,
            )

        status, _body = await guard.run(
            tenant_id=tenant_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=failing_then_succeeding,
        )
        assert status == 201
        assert attempts == 2, "the retry after an unexpected failure must actually re-execute"

    async def test_a_cached_error_response_is_replayed_like_a_success_response(
        self, session_factory
    ) -> None:
        """An expected, already-shaped 4xx (the router's own
        ``execute`` callable catching its module's domain exception via
        ``build_error_response``) is cached and replayed exactly like a
        2xx -- a retry always gets the same answer."""
        tenant_id = generate_ulid()
        await _seed_tenant(session_factory, tenant_id)
        guard = IdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})
        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 409, {"error": {"code": "SOME_CONFLICT", "message": "already exists"}}

        first = await guard.run(
            tenant_id=tenant_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=execute,
        )
        second = await guard.run(
            tenant_id=tenant_id,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=execute,
        )

        assert (
            first
            == second
            == (409, {"error": {"code": "SOME_CONFLICT", "message": "already exists"}})
        )
        assert calls == 1

    async def test_different_tenants_do_not_share_idempotency_keys(self, session_factory) -> None:
        tenant_a = generate_ulid()
        tenant_b = generate_ulid()
        await _seed_tenant(session_factory, tenant_a)
        await _seed_tenant(session_factory, tenant_b)
        guard = IdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})
        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"call": calls}

        result_a = await guard.run(
            tenant_id=tenant_a,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=execute,
        )
        result_b = await guard.run(
            tenant_id=tenant_b,
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=execute,
        )

        assert calls == 2, "the same key in two different tenants must not collide"
        assert result_a != result_b
