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


class InvalidTenantStatusTransitionError(IdentityDomainError):
    error_code = "INVALID_TENANT_STATUS_TRANSITION"

    def __init__(self, tenant_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Tenant '{tenant_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.tenant_id = tenant_id
        self.from_status = from_status
        self.to_status = to_status


class TenantLegalNameConflictError(IdentityDomainError):
    error_code = "TENANT_LEGAL_NAME_CONFLICT"

    def __init__(self, legal_name: str) -> None:
        super().__init__(f"A tenant with legal name '{legal_name}' already exists.")
        self.legal_name = legal_name


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


class InvalidAccessTokenError(IdentityDomainError):
    """Raised by auth middleware when an access token is missing, malformed,
    expired, or its ``permission_version`` no longer matches the live value
    (Technical Architecture v2.0 Group C)."""

    error_code = "INVALID_ACCESS_TOKEN"

    def __init__(self, reason: str = "Access token is missing, invalid, or expired.") -> None:
        super().__init__(reason)


class InsufficientPrivilegesError(IdentityDomainError):
    """Raised when an authenticated caller lacks the privilege a
    (temporary, non-RBAC — see modules/identity/README.md) endpoint
    requires, e.g. platform-admin-only tenant lifecycle operations."""

    error_code = "INSUFFICIENT_PRIVILEGES"

    def __init__(self) -> None:
        super().__init__("This action requires platform administrator privileges.")


class SubscriptionNotFoundError(IdentityDomainError):
    error_code = "SUBSCRIPTION_NOT_FOUND"

    def __init__(self, tenant_id: str) -> None:
        super().__init__(f"Tenant '{tenant_id}' has no subscription.")
        self.tenant_id = tenant_id


# --- RBAC Foundation (Sprint 5, Step 2) -------------------------------------


class RoleNotFoundError(IdentityDomainError):
    error_code = "ROLE_NOT_FOUND"

    def __init__(self, role_id: str) -> None:
        super().__init__(f"Role '{role_id}' does not exist.")
        self.role_id = role_id


class PermissionNotFoundError(IdentityDomainError):
    error_code = "PERMISSION_NOT_FOUND"

    def __init__(self, permission_code: str) -> None:
        super().__init__(f"Permission '{permission_code}' does not exist.")
        self.permission_code = permission_code


class RoleNameConflictError(IdentityDomainError):
    error_code = "ROLE_NAME_CONFLICT"

    def __init__(self, name: str) -> None:
        super().__init__(f"A role named '{name}' already exists at this scope.")
        self.name = name


class InvalidRoleLifecycleTransitionError(IdentityDomainError):
    error_code = "INVALID_ROLE_LIFECYCLE_TRANSITION"

    def __init__(self, role_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Role '{role_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.role_id = role_id
        self.from_status = from_status
        self.to_status = to_status


class InvalidPermissionStateTransitionError(IdentityDomainError):
    error_code = "INVALID_PERMISSION_STATE_TRANSITION"

    def __init__(self, permission_code: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Permission '{permission_code}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.permission_code = permission_code
        self.from_status = from_status
        self.to_status = to_status


class RoleNotActiveError(IdentityDomainError):
    """Raised when a grant is attempted against a retired (inactive) role
    — RBAC Foundation Architecture SS4.1."""

    error_code = "ROLE_NOT_ACTIVE"

    def __init__(self, role_id: str) -> None:
        super().__init__(f"Role '{role_id}' is retired and cannot be granted.")
        self.role_id = role_id


class DuplicateRoleAssignmentError(IdentityDomainError):
    """Raised when a ``(user_id, role_id, branch_id)`` grant already
    exists — the application-layer mirror of the database's own
    ``UNIQUE NULLS NOT DISTINCT`` constraint (RBAC Foundation
    Architecture SS13.3), so a duplicate is caught with a clean domain
    error before ever reaching Postgres where possible, and mapped from
    the resulting ``IntegrityError`` where a race makes that
    impossible."""

    error_code = "DUPLICATE_ROLE_ASSIGNMENT"

    def __init__(self, user_id: str, role_id: str, branch_id: str | None) -> None:
        scope = f"branch '{branch_id}'" if branch_id else "tenant-wide"
        super().__init__(f"User '{user_id}' already holds role '{role_id}' at {scope} scope.")
        self.user_id = user_id
        self.role_id = role_id
        self.branch_id = branch_id


class UserRoleNotFoundError(IdentityDomainError):
    error_code = "USER_ROLE_NOT_FOUND"

    def __init__(self, user_role_id: str) -> None:
        super().__init__(f"Role assignment '{user_role_id}' does not exist.")
        self.user_role_id = user_role_id


class InsufficientGrantAuthorityError(IdentityDomainError):
    """Raised by ``RoleGrantPolicy`` (RBAC Foundation Architecture SS16.1)
    when a grant would exceed the granter's own scope (they hold
    ``roles.assign`` at a narrower scope than the grant they're
    attempting) or delegate a permission they don't themselves hold.
    Distinct from ``INSUFFICIENT_PRIVILEGES`` (the pre-existing,
    unrelated platform-admin gate) — this is specifically about RBAC's
    own privilege-escalation ceiling."""

    error_code = "INSUFFICIENT_GRANT_AUTHORITY"

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
