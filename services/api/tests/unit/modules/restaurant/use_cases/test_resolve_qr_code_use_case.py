"""Unit tests for ResolveQRCodeUseCase (Sprint 5 Step 4.7) -- in-memory
fakes, no network/DB access.

The rate limiter's own atomic-upsert/concurrency correctness cannot be
proven with a fake (it depends on real Postgres row-locking under
``ON CONFLICT``) -- that lives in the integration suite. These tests
cover the use case's own logic: enumeration collapse (not-found and
revoked both return ``None``, indistinguishably), the check-before-
lookup/record-failure-after-lookup call sequence, and that a
``RateLimitExceededError`` from either rate-limiter call propagates
unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.use_cases import ResolveQRCodeUseCase
from restaurant_os_api.modules.restaurant.domain.entities import QRCode, QRCodeStatus
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeQRResolutionRateLimiter,
    InMemoryQRCodeRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE1"
QR_CODE_ID = "01ARZ3NDEKTSV4RRFFQ6QRCOD1"
SOURCE_IP = "203.0.113.42"


def _qr_code(**overrides) -> QRCode:
    defaults = {
        "id": QR_CODE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_id": TABLE_ID,
        "token": "a-real-opaque-token",
        "status": QRCodeStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return QRCode(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _use_case(qr_code_repo, rate_limiter) -> ResolveQRCodeUseCase:
    return ResolveQRCodeUseCase(
        session_factory=_session_factory(),
        qr_code_repository_factory=lambda _s: qr_code_repo,
        rate_limiter=rate_limiter,
    )


class TestResolveQRCodeUseCase:
    async def test_an_active_token_resolves_to_the_three_identifiers(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        result = await use_case.execute("a-real-opaque-token", SOURCE_IP)

        assert result is not None
        assert result.tenant_id == TENANT_ID
        assert result.branch_id == BRANCH_ID
        assert result.table_id == TABLE_ID

    async def test_a_nonexistent_token_returns_none(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository()
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        result = await use_case.execute("no-such-token", SOURCE_IP)
        assert result is None

    async def test_a_revoked_token_returns_none(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code(status=QRCodeStatus.REVOKED)})
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        result = await use_case.execute("a-real-opaque-token", SOURCE_IP)
        assert result is None

    async def test_not_found_and_revoked_are_indistinguishable_to_the_caller(self) -> None:
        """Enumeration protection at the use-case boundary: both
        failure modes must produce the exact same return value, with
        no exception, code, or attribute that would let a caller tell
        them apart."""
        missing_repo = InMemoryQRCodeRepository()
        revoked_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code(status=QRCodeStatus.REVOKED)})

        missing_result = await _use_case(missing_repo, FakeQRResolutionRateLimiter()).execute(
            "whatever", SOURCE_IP
        )
        revoked_result = await _use_case(revoked_repo, FakeQRResolutionRateLimiter()).execute(
            "a-real-opaque-token", SOURCE_IP
        )

        assert missing_result is revoked_result is None
        assert type(missing_result) is type(revoked_result)

    async def test_check_is_called_before_the_lookup(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        await use_case.execute("a-real-opaque-token", SOURCE_IP)

        assert rate_limiter.check_calls == [(SOURCE_IP, "a-real-opaque-token")]

    async def test_record_failure_is_called_only_when_resolution_fails(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        await use_case.execute("a-real-opaque-token", SOURCE_IP)

        assert rate_limiter.record_failure_calls == []

    async def test_record_failure_is_called_on_a_missing_token(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository()
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        await use_case.execute("no-such-token", SOURCE_IP)

        assert rate_limiter.record_failure_calls == [(SOURCE_IP, "no-such-token")]

    async def test_record_failure_is_called_on_a_revoked_token(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code(status=QRCodeStatus.REVOKED)})
        rate_limiter = FakeQRResolutionRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        await use_case.execute("a-real-opaque-token", SOURCE_IP)

        assert rate_limiter.record_failure_calls == [(SOURCE_IP, "a-real-opaque-token")]

    async def test_a_rate_limit_at_check_time_propagates_and_skips_the_lookup(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        rate_limiter = FakeQRResolutionRateLimiter(raise_on_check=True)
        use_case = _use_case(qr_code_repo, rate_limiter)

        with pytest.raises(RateLimitExceededError):
            await use_case.execute("a-real-opaque-token", SOURCE_IP)

        # record_failure is never reached -- check() raised first.
        assert rate_limiter.record_failure_calls == []

    async def test_a_rate_limit_at_record_failure_time_propagates(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository()
        rate_limiter = FakeQRResolutionRateLimiter(raise_on_record_failure=True)
        use_case = _use_case(qr_code_repo, rate_limiter)

        with pytest.raises(RateLimitExceededError):
            await use_case.execute("no-such-token", SOURCE_IP)
