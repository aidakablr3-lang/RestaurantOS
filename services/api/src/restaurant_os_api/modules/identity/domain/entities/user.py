"""User entity.

Data Architecture v2.0 SS3.1/SS5.3. Password/PIN hashes are opaque strings
to the domain layer — hashing and verification are Infrastructure-layer
concerns reached only through the ``PasswordHasher`` application port
(Technical Architecture v2.0 SS2.2's dependency rule: Domain never imports
Infrastructure).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.identity.domain.exceptions import UserNotActiveError


class UserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


@dataclass(slots=True)
class User:
    id: str
    tenant_id: str
    email: str | None
    phone: str | None
    password_hash: str | None
    pin_hash: str | None
    permission_version: int
    status: UserStatus
    created_at: datetime
    is_platform_admin: bool = False

    def ensure_can_authenticate(self) -> None:
        """Raise if this user is not allowed to start a new session.

        This is the domain-layer half of Technical Architecture v2.0
        Group C's immediate-deactivation guarantee: a deactivated user
        must never be issued a *new* session, regardless of how their
        credentials were obtained. Revoking an already-issued session is
        a separate, application-layer concern (LogoutUserUseCase /
        the permission-version bump on deactivation).
        """
        if self.status != UserStatus.ACTIVE:
            raise UserNotActiveError(self.id, self.status.value)

    def has_password_credential(self) -> bool:
        return self.password_hash is not None

    def has_pin_credential(self) -> bool:
        return self.pin_hash is not None
