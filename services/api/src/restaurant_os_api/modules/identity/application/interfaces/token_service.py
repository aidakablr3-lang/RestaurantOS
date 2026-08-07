"""Application-layer port for token issuance and refresh-token handling.

Technical Architecture v2.0 SS8.3: access tokens carry identity claims
only (no roles/permissions — Group C's fix for the immediate-revocation
gap), and refresh tokens are opaque, high-entropy strings whose *hash* is
what gets persisted (Data Architecture v2.0 SS11.4) — this interface
never exposes a way to construct a usable refresh token from a hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Everything an access token carries — identity only, per Group C.

    Deliberately excludes roles/permissions: a request's current
    permission set is resolved per-request against the live
    ``permission_version`` (Technical Architecture v2.0 Group C), not
    trusted from a token that could be up to ``access_ttl_seconds`` old.
    """

    subject_user_id: str
    tenant_id: str
    session_id: str
    device_id: str | None
    permission_version: int


class TokenDecodeError(Exception):
    """Raised when an access token is malformed, expired, or has an
    invalid signature. Deliberately generic — the presentation-layer
    auth middleware (a follow-up PR) maps this to a single 401 response
    without distinguishing the reason to the caller.
    """


class TokenService(Protocol):
    def issue_access_token(self, claims: AccessTokenClaims) -> str: ...

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        """Raise ``TokenDecodeError`` if the token is invalid or expired."""
        ...

    def generate_refresh_token(self) -> str:
        """Return a new, high-entropy, opaque refresh token (raw value).

        This is the only place the raw value exists outside the client
        that receives it — the caller must hash it via
        ``hash_refresh_token`` before persisting anything.
        """
        ...

    def hash_refresh_token(self, raw_token: str) -> str:
        """Return a deterministic, non-reversible digest of a refresh token.

        Not Argon2id: a refresh token is already a high-entropy random
        value, not a low-entropy human-chosen secret, so a fast
        cryptographic hash (used here for exact-match lookup by digest)
        is the correct tool — Argon2id's deliberate slowness exists to
        resist brute-forcing a small password space, which does not
        apply here.
        """
        ...
