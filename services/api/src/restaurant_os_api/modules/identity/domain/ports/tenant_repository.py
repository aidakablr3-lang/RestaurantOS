"""Repository port for Tenant.

A ``Protocol``, not an ABC — Technical Architecture v2.0 SS5.2/SS6.3: the
Application layer depends on this interface, and the Infrastructure
layer's SQLAlchemy implementation satisfies it structurally, with no
inheritance coupling between the two.
"""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Tenant


class TenantRepository(Protocol):
    async def get_by_id(self, tenant_id: str) -> Tenant | None: ...
