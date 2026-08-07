"""Session entity — the durable, revocable half of the auth token pair.

Technical Architecture v2.0 SS8.3: access tokens are short-lived and
stateless; refresh tokens are long-lived and stateful, tracked here so a
specific session can be force-revoked (device lost, user logged out
elsewhere, account deactivated) without needing to track every access
token ever issued.

Only a *hash* of the refresh token is ever stored (Data Architecture v2.0
SS11.4) — this entity never holds a usable bearer credential.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidRefreshTokenError,
    SessionRevokedError,
)


@dataclass(slots=True)
class Session:
    id: str
    user_id: str
    device_id: str | None
    refresh_token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    def ensure_valid_for_refresh(self) -> None:
        """Raise if this session may not be used to mint a new access token."""
        if self.revoked_at is not None:
            raise SessionRevokedError(self.id)
        if datetime.now(UTC) >= self.expires_at:
            raise InvalidRefreshTokenError()

    def revoke(self, *, at: datetime | None = None) -> None:
        self.revoked_at = at or datetime.now(UTC)
