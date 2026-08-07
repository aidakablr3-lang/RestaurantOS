from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.domain.entities import User, UserStatus
from restaurant_os_api.modules.identity.domain.exceptions import UserNotActiveError


def _make_user(
    status: UserStatus = UserStatus.ACTIVE,
    password_hash: str | None = "hashed::secret",
    pin_hash: str | None = None,
) -> User:
    return User(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
        tenant_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        email="owner@example.com",
        phone=None,
        password_hash=password_hash,
        pin_hash=pin_hash,
        permission_version=1,
        status=status,
        created_at=datetime.now(UTC),
    )


def test_active_user_can_authenticate() -> None:
    _make_user(status=UserStatus.ACTIVE).ensure_can_authenticate()  # must not raise


@pytest.mark.parametrize("status", [UserStatus.INVITED, UserStatus.DEACTIVATED])
def test_non_active_user_cannot_authenticate(status: UserStatus) -> None:
    with pytest.raises(UserNotActiveError) as exc_info:
        _make_user(status=status).ensure_can_authenticate()
    assert exc_info.value.status == status.value


def test_has_password_credential_reflects_password_hash_presence() -> None:
    assert _make_user(password_hash="hashed::x").has_password_credential() is True
    assert _make_user(password_hash=None, pin_hash="1234").has_password_credential() is False


def test_has_pin_credential_reflects_pin_hash_presence() -> None:
    assert _make_user(pin_hash="hashed::1234").has_pin_credential() is True
    assert _make_user(pin_hash=None).has_pin_credential() is False
