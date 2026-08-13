"""Unit tests for GuestResolveQRCodeUseCase (guest ordering).

Mirrors ``test_resolve_qr_code_use_case.py``'s own coverage of
enumeration collapse, minus the ``record_failure`` calls
``ResolveQRCodeUseCase`` makes -- ``GuestOrderRateLimiter`` tracks no
separate failed-count (see that limiter's own docstring).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.restaurant.application.use_cases import GuestResolveQRCodeUseCase
from restaurant_os_api.modules.restaurant.domain.entities import QRCode, QRCodeStatus
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeGuestOrderRateLimiter,
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


def _use_case(qr_code_repo, rate_limiter) -> GuestResolveQRCodeUseCase:
    return GuestResolveQRCodeUseCase(
        session_factory=fake_session_factory_returning(FakeAsyncSession()),
        qr_code_repository_factory=lambda _s: qr_code_repo,
        rate_limiter=rate_limiter,
    )


class TestGuestResolveQRCodeUseCase:
    async def test_an_active_token_resolves_to_the_three_identifiers(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        use_case = _use_case(qr_code_repo, FakeGuestOrderRateLimiter())

        result = await use_case.execute("a-real-opaque-token", SOURCE_IP)

        assert result is not None
        assert result.tenant_id == TENANT_ID
        assert result.branch_id == BRANCH_ID
        assert result.table_id == TABLE_ID

    async def test_a_nonexistent_token_returns_none(self) -> None:
        use_case = _use_case(InMemoryQRCodeRepository(), FakeGuestOrderRateLimiter())

        result = await use_case.execute("no-such-token", SOURCE_IP)
        assert result is None

    async def test_a_revoked_token_returns_none(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code(status=QRCodeStatus.REVOKED)})
        use_case = _use_case(qr_code_repo, FakeGuestOrderRateLimiter())

        result = await use_case.execute("a-real-opaque-token", SOURCE_IP)
        assert result is None

    async def test_check_is_called_before_the_lookup(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        rate_limiter = FakeGuestOrderRateLimiter()
        use_case = _use_case(qr_code_repo, rate_limiter)

        await use_case.execute("a-real-opaque-token", SOURCE_IP)

        assert rate_limiter.check_calls == [(SOURCE_IP, "a-real-opaque-token")]

    async def test_a_rate_limit_at_check_time_propagates_and_skips_the_lookup(self) -> None:
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        use_case = _use_case(qr_code_repo, FakeGuestOrderRateLimiter(raise_on_check=True))

        with pytest.raises(RateLimitExceededError):
            await use_case.execute("a-real-opaque-token", SOURCE_IP)
