"""Domain exceptions for the identity module.

These carry no HTTP concepts (Technical Architecture v2.0 SS5.4) — the
presentation layer's global exception handler maps each of these to an
HTTP status and the standard error envelope. Every exception exposes a
stable, machine-readable ``error_code`` so callers can branch on exact
meaning rather than on message text.
"""

from __future__ import annotations


class IdentityDomainError(Exception):
    """Base class for every domain exception raised by the identity module."""

    error_code: str = "IDENTITY_DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TenantNotFoundError(IdentityDomainError):
    error_code = "TENANT_NOT_FOUND"

    def __init__(self, tenant_id: str) -> None:
        super().__init__(f"Tenant '{tenant_id}' does not exist.")
        self.tenant_id = tenant_id


class TenantNotActiveError(IdentityDomainError):
    error_code = "TENANT_NOT_ACTIVE"

    def __init__(self, tenant_id: str, status: str) -> None:
        super().__init__(f"Tenant '{tenant_id}' is not active (status='{status}').")
        self.tenant_id = tenant_id
        self.status = status


class UserNotFoundError(IdentityDomainError):
    error_code = "USER_NOT_FOUND"

    def __init__(self, identifier: str) -> None:
        super().__init__(f"User '{identifier}' does not exist.")
        self.identifier = identifier


class UserNotActiveError(IdentityDomainError):
    error_code = "USER_NOT_ACTIVE"

    def __init__(self, user_id: str, status: str) -> None:
        super().__init__(f"User '{user_id}' is not active (status='{status}').")
        self.user_id = user_id
        self.status = status


class InvalidCredentialsError(IdentityDomainError):
    """Raised for any authentication failure.

    Deliberately does not distinguish "wrong password" from "user not
    found" in its message — the distinction exists internally (for
    logging/rate-limiting) but must never leak to the caller, since doing
    so would let an attacker enumerate valid accounts.
    """

    error_code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class InvalidRefreshTokenError(IdentityDomainError):
    error_code = "INVALID_REFRESH_TOKEN"

    def __init__(self) -> None:
        super().__init__("Refresh token is invalid, expired, or has already been used.")


class SessionRevokedError(IdentityDomainError):
    error_code = "SESSION_REVOKED"

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' has been revoked.")
        self.session_id = session_id


class InvalidEmailAddressError(IdentityDomainError):
    error_code = "INVALID_EMAIL_ADDRESS"

    def __init__(self, value: str) -> None:
        super().__init__(f"'{value}' is not a valid email address.")
        self.value = value
