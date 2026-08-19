"""OwnerActivationToken entity.

Phase 1 design doc SSA.4: the one-time credential that lets a
provisioned tenant's Owner (created with ``password_hash=None``,
``status=INVITED`` -- see ``TenantProvisioningService.provision()``) set
their first password and move to ``ACTIVE``. Modeled directly on
``Session``: only a *hash* of the token is ever stored, mirroring
``Session.refresh_token_hash``'s own "this entity never holds a usable
bearer credential" guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class OwnerActivationToken:
    id: str
    tenant_id: str
    user_id: str
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    used_at: datetime | None

    def is_usable(self, *, at: datetime | None = None) -> bool:
        now = at or datetime.now(UTC)
        return self.used_at is None and now < self.expires_at

    def mark_used(self, *, at: datetime | None = None) -> None:
        self.used_at = at or datetime.now(UTC)
