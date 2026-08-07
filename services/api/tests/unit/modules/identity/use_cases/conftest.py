from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.domain.entities import (
    Tenant,
    TenantStatus,
    TenantTier,
    User,
    UserStatus,
)
from tests.unit.modules.identity.fakes import (
    FakeAsyncSession,
    FakePasswordHasher,
    FakeTokenService,
    InMemorySessionRepository,
    InMemoryTenantRepository,
    InMemoryUserRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
USER_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
USER_EMAIL = "owner@example.com"
USER_PASSWORD = "correct horse battery staple"


@pytest.fixture
def fake_session() -> FakeAsyncSession:
    return FakeAsyncSession()


@pytest.fixture
def session_factory(fake_session: FakeAsyncSession):
    return fake_session_factory_returning(fake_session)


@pytest.fixture
def active_tenant() -> Tenant:
    return Tenant(
        id=TENANT_ID,
        legal_name="Acme Restaurants Inc.",
        display_name="Acme",
        tenant_tier=TenantTier.SHARED,
        status=TenantStatus.ACTIVE,
        default_currency_code="USD",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def password_hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def active_user(password_hasher: FakePasswordHasher) -> User:
    return User(
        id=USER_ID,
        tenant_id=TENANT_ID,
        email=USER_EMAIL,
        phone=None,
        password_hash=password_hasher.hash(USER_PASSWORD),
        pin_hash=None,
        permission_version=1,
        status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def tenant_repository(active_tenant: Tenant) -> InMemoryTenantRepository:
    return InMemoryTenantRepository({active_tenant.id: active_tenant})


@pytest.fixture
def user_repository(active_user: User) -> InMemoryUserRepository:
    return InMemoryUserRepository({active_user.id: active_user})


@pytest.fixture
def session_repository() -> InMemorySessionRepository:
    return InMemorySessionRepository()


@pytest.fixture
def token_service() -> FakeTokenService:
    return FakeTokenService()
