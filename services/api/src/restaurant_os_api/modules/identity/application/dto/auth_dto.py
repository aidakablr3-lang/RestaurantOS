"""Application-layer DTOs for the login/refresh/logout use cases.

Technical Architecture v2.0 SS5.6: these are distinct from the
presentation layer's Pydantic request/response schemas — a use case
never receives or returns a Pydantic model, so its unit tests never need
FastAPI/Pydantic installed to run (Data Architecture v2.0 SS13, "unit
tests must run with no network/DB access").
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoginRequestDTO:
    tenant_id: str
    email: str
    password: str
    device_id: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshRequestDTO:
    tenant_id: str
    refresh_token: str
    device_id: str | None = None


@dataclass(frozen=True, slots=True)
class LogoutRequestDTO:
    tenant_id: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class TokenPairDTO:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipalDTO:
    """The result of successfully verifying an access token — everything
    a protected route needs to know about the caller, resolved and
    validated in one pass (Sprint 4.1's `VerifyAccessTokenUseCase`)."""

    user_id: str
    tenant_id: str
    session_id: str
    device_id: str | None
    is_platform_admin: bool
