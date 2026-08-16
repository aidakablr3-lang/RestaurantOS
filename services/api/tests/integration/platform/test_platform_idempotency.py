"""Integration tests for PlatformIdempotencyGuard against real PostgreSQL.

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Mirrors
test_idempotency.py's coverage for IdempotencyGuard, minus the
per-tenant-isolation case (there is no tenant dimension here by
design -- see the guard's own docstring for why) and minus any tenant
seeding: platform_idempotency_keys carries no tenant_id/FK, which is
the entire point of this guard existing separately.
"""

from __future__ import annotations

import pytest

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.platform.idempotency import (
    IdempotencyKeyConflictError,
    IdempotentRequestInProgressError,
    PlatformIdempotencyGuard,
    fingerprint_request,
)


class TestPlatformIdempotencyGuard:
    async def test_a_fresh_key_executes_the_use_case_and_returns_its_result(
        self, session_factory
    ) -> None:
        guard = PlatformIdempotencyGuard(session_factory)
        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"created": True}

        status, body = await guard.run(
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
        guard = PlatformIdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})
        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"created": True, "call": calls}

        first = await guard.run(
            idempotency_key=key, request_fingerprint=fingerprint, execute=execute
        )
        second = await guard.run(
            idempotency_key=key, request_fingerprint=fingerprint, execute=execute
        )

        assert first == second
        assert calls == 1, "the use case must not run twice for a replayed request"

    async def test_the_same_key_with_a_different_body_is_a_dedicated_conflict(
        self, session_factory
    ) -> None:
        guard = PlatformIdempotencyGuard(session_factory)
        key = generate_ulid()

        async def execute() -> tuple[int, dict]:
            return 201, {"created": True}

        await guard.run(
            idempotency_key=key,
            request_fingerprint=fingerprint_request({"a": 1}),
            execute=execute,
        )

        with pytest.raises(IdempotencyKeyConflictError):
            await guard.run(
                idempotency_key=key,
                request_fingerprint=fingerprint_request({"a": 2}),
                execute=execute,
            )

    async def test_a_concurrent_duplicate_cannot_execute_the_use_case_twice(
        self, session_factory
    ) -> None:
        guard = PlatformIdempotencyGuard(session_factory)
        key = generate_ulid()
        fingerprint = fingerprint_request({"a": 1})

        claimed = await guard._try_claim(key, fingerprint)
        assert claimed is True

        calls = 0

        async def execute() -> tuple[int, dict]:
            nonlocal calls
            calls += 1
            return 201, {"created": True}

        with pytest.raises(IdempotentRequestInProgressError):
            await guard.run(idempotency_key=key, request_fingerprint=fingerprint, execute=execute)
        assert calls == 0, "a request already in flight must never run a second execution"

    async def test_an_unexpected_exception_releases_the_claim_for_a_fresh_retry(
        self, session_factory
    ) -> None:
        guard = PlatformIdempotencyGuard(session_factory)
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
                idempotency_key=key,
                request_fingerprint=fingerprint,
                execute=failing_then_succeeding,
            )

        status, _body = await guard.run(
            idempotency_key=key,
            request_fingerprint=fingerprint,
            execute=failing_then_succeeding,
        )
        assert status == 201
        assert attempts == 2, "the retry after an unexpected failure must actually re-execute"
