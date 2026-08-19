"""Unit tests for GetOwnerActivationTokenStatusUseCase (Phase 1 design
doc §A.4 -- added so ProvisionTenantStep.verify() can confirm the
just-issued activation token is still usable)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from restaurant_os_api.modules.identity.application.use_cases import (
    GetOwnerActivationTokenStatusUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import OwnerActivationToken
from tests.unit.modules.identity.fakes import InMemoryOwnerActivationTokenRepository
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID


def _use_case(session_factory, token_repo) -> GetOwnerActivationTokenStatusUseCase:
    return GetOwnerActivationTokenStatusUseCase(
        session_factory=session_factory,
        owner_activation_token_repository_factory=lambda _s: token_repo,
    )


async def test_true_when_an_unexpired_unused_token_exists(session_factory) -> None:
    token_repo = InMemoryOwnerActivationTokenRepository()
    await token_repo.create(
        OwnerActivationToken(
            id="01ARZ3NDEKTSV4RRFFQ6TOKEN0",
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            token_hash="irrelevant-hash",
            issued_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            used_at=None,
        )
    )

    assert await _use_case(session_factory, token_repo).execute(TENANT_ID, USER_ID) is True


async def test_false_when_no_token_exists_for_the_user(session_factory) -> None:
    token_repo = InMemoryOwnerActivationTokenRepository()

    assert await _use_case(session_factory, token_repo).execute(TENANT_ID, USER_ID) is False


async def test_false_when_the_token_is_expired(session_factory) -> None:
    token_repo = InMemoryOwnerActivationTokenRepository()
    await token_repo.create(
        OwnerActivationToken(
            id="01ARZ3NDEKTSV4RRFFQ6TOKEN0",
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            token_hash="irrelevant-hash",
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
            used_at=None,
        )
    )

    assert await _use_case(session_factory, token_repo).execute(TENANT_ID, USER_ID) is False


async def test_false_when_the_token_is_already_used(session_factory) -> None:
    token_repo = InMemoryOwnerActivationTokenRepository()
    await token_repo.create(
        OwnerActivationToken(
            id="01ARZ3NDEKTSV4RRFFQ6TOKEN0",
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            token_hash="irrelevant-hash",
            issued_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            used_at=datetime.now(UTC),
        )
    )

    assert await _use_case(session_factory, token_repo).execute(TENANT_ID, USER_ID) is False


async def test_false_when_the_token_belongs_to_a_different_user(session_factory) -> None:
    token_repo = InMemoryOwnerActivationTokenRepository()
    await token_repo.create(
        OwnerActivationToken(
            id="01ARZ3NDEKTSV4RRFFQ6TOKEN0",
            tenant_id=TENANT_ID,
            user_id="01ARZ3NDEKTSV4RRFFQ6OTHRUS",
            token_hash="irrelevant-hash",
            issued_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            used_at=None,
        )
    )

    assert await _use_case(session_factory, token_repo).execute(TENANT_ID, USER_ID) is False
