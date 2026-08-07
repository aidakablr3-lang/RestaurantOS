"""RS256 JWT access tokens + opaque refresh tokens.

Technical Architecture v2.0 SS8.3: asymmetric (RS256) signing, not
symmetric (HS256) — the public key can later be distributed to the
WebSocket service and other processes to verify tokens independently,
without sharing the private signing secret across every service.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt as _pyjwt

from restaurant_os_api.modules.identity.application.interfaces.token_service import (
    AccessTokenClaims,
    TokenDecodeError,
)

_ALGORITHM = "RS256"
_REFRESH_TOKEN_BYTES = 32  # 256 bits of entropy


class JWTTokenService:
    """Implements the ``TokenService`` application port."""

    def __init__(
        self,
        *,
        private_key: str,
        public_key: str,
        issuer: str,
        access_ttl_seconds: int,
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._issuer = issuer
        self._access_ttl_seconds = access_ttl_seconds

    def issue_access_token(self, claims: AccessTokenClaims) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": claims.subject_user_id,
            "tenant_id": claims.tenant_id,
            "session_id": claims.session_id,
            "device_id": claims.device_id,
            "permission_version": claims.permission_version,
            "iss": self._issuer,
            "iat": now,
            "exp": now + timedelta(seconds=self._access_ttl_seconds),
        }
        return _pyjwt.encode(payload, self._private_key, algorithm=_ALGORITHM)

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = _pyjwt.decode(
                token,
                self._public_key,
                algorithms=[_ALGORITHM],
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "tenant_id", "session_id"]},
            )
        except _pyjwt.PyJWTError as exc:
            raise TokenDecodeError(str(exc)) from exc

        return AccessTokenClaims(
            subject_user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            session_id=payload["session_id"],
            device_id=payload.get("device_id"),
            permission_version=payload["permission_version"],
        )

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)

    def hash_refresh_token(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
