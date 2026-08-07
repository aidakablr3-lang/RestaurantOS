from datetime import UTC, datetime, timedelta

import pytest

from restaurant_os_api.modules.identity.domain.entities import Session
from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidRefreshTokenError,
    SessionRevokedError,
)


def _make_session(*, expires_in: timedelta = timedelta(days=30), revoked: bool = False) -> Session:
    now = datetime.now(UTC)
    return Session(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAX",
        tenant_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        user_id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
        device_id=None,
        refresh_token_hash="hashed::token",
        issued_at=now,
        expires_at=now + expires_in,
        revoked_at=now if revoked else None,
    )


def test_valid_session_passes_refresh_check() -> None:
    _make_session().ensure_valid_for_refresh()  # must not raise


def test_revoked_session_raises_session_revoked_error() -> None:
    with pytest.raises(SessionRevokedError):
        _make_session(revoked=True).ensure_valid_for_refresh()


def test_expired_session_raises_invalid_refresh_token_error() -> None:
    with pytest.raises(InvalidRefreshTokenError):
        _make_session(expires_in=timedelta(seconds=-1)).ensure_valid_for_refresh()


def test_revoke_sets_revoked_at() -> None:
    session = _make_session()
    assert session.revoked_at is None
    session.revoke()
    assert session.revoked_at is not None


def test_revoke_accepts_explicit_timestamp() -> None:
    session = _make_session()
    fixed_time = datetime(2026, 1, 1, tzinfo=UTC)
    session.revoke(at=fixed_time)
    assert session.revoked_at == fixed_time
