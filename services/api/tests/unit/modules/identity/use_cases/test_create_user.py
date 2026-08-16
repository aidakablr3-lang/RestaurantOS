"""Unit tests for CreateUserUseCase -- the API counterpart to
scripts/create_user.py. Covers: successful creation with a generated
password, successful creation with a caller-supplied password (no
password echoed back), the email-conflict guard, and that a UserCreated
event is published.
"""

from __future__ import annotations

import pytest

from restaurant_os_api.modules.identity.application.dto import CreateUserRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import CreateUserUseCase
from restaurant_os_api.modules.identity.domain.events import UserCreated
from restaurant_os_api.modules.identity.domain.exceptions import UserEmailConflictError
from tests.unit.modules.identity.fakes import (
    FakeOutboxWriter,
    FakePasswordHasher,
    InMemoryUserRepository,
)
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID

CREATOR_ID = "01ARZ3NDEKTSV4RRFFQ6CREATR"


class _Fixture:
    def __init__(self) -> None:
        self.user_repo = InMemoryUserRepository()
        self.outbox = FakeOutboxWriter()
        self.password_hasher = FakePasswordHasher()

    def use_case(self, session_factory) -> CreateUserUseCase:
        return CreateUserUseCase(
            session_factory=session_factory,
            user_repository_factory=lambda _s: self.user_repo,
            password_hasher=self.password_hasher,
            outbox_writer_factory=lambda _s: self.outbox,
        )


@pytest.fixture
def fixture() -> _Fixture:
    return _Fixture()


async def test_creates_an_active_user_with_a_generated_password(
    fixture: _Fixture, session_factory
) -> None:
    use_case = fixture.use_case(session_factory)

    result = await use_case.execute(
        TENANT_ID,
        CreateUserRequestDTO(creator_user_id=CREATOR_ID, email="waiter@example.com"),
    )

    assert result.email == "waiter@example.com"
    assert result.status == "active"
    assert result.generated_password is not None
    stored = await fixture.user_repo.get_by_email(TENANT_ID, "waiter@example.com")
    assert stored is not None
    assert fixture.password_hasher.verify(result.generated_password, stored.password_hash)


async def test_creates_a_user_with_a_caller_supplied_password_and_does_not_echo_it_back(
    fixture: _Fixture, session_factory
) -> None:
    use_case = fixture.use_case(session_factory)

    result = await use_case.execute(
        TENANT_ID,
        CreateUserRequestDTO(
            creator_user_id=CREATOR_ID,
            email="waiter@example.com",
            password="a specific known password",
        ),
    )

    assert result.generated_password is None
    stored = await fixture.user_repo.get_by_email(TENANT_ID, "waiter@example.com")
    assert stored is not None
    assert fixture.password_hasher.verify("a specific known password", stored.password_hash)


async def test_duplicate_email_in_the_same_tenant_is_rejected(
    fixture: _Fixture, session_factory
) -> None:
    use_case = fixture.use_case(session_factory)
    await use_case.execute(
        TENANT_ID, CreateUserRequestDTO(creator_user_id=CREATOR_ID, email="dup@example.com")
    )

    with pytest.raises(UserEmailConflictError):
        await use_case.execute(
            TENANT_ID, CreateUserRequestDTO(creator_user_id=CREATOR_ID, email="dup@example.com")
        )


async def test_creating_a_user_publishes_user_created(fixture: _Fixture, session_factory) -> None:
    use_case = fixture.use_case(session_factory)

    result = await use_case.execute(
        TENANT_ID,
        CreateUserRequestDTO(creator_user_id=CREATOR_ID, email="waiter@example.com"),
    )

    assert len(fixture.outbox.published) == 1
    tenant_id, event = fixture.outbox.published[0]
    assert tenant_id == TENANT_ID
    assert isinstance(event, UserCreated)
    assert event.user_id == result.id
    assert event.created_by_user_id == CREATOR_ID
