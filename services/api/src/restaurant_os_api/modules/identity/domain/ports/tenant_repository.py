"""Repository port for Tenant.

A ``Protocol``, not an ABC — Technical Architecture v2.0 SS5.2/SS6.3: the
Application layer depends on this interface, and the Infrastructure
layer's SQLAlchemy implementation satisfies it structurally, with no
inheritance coupling between the two.
"""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Tenant, TenantStatus


class TenantRepository(Protocol):
    async def get_by_id(self, tenant_id: str) -> Tenant | None: ...

    async def get_by_legal_name(self, legal_name: str) -> Tenant | None:
        """Used by onboarding to reject a duplicate legal name before
        attempting an insert — a friendlier failure than a raw
        constraint violation, and the check a real uniqueness constraint
        backs at the database layer regardless (belt-and-suspenders,
        consistent with Data Architecture v2.0's isolation philosophy
        applied here to data quality, not tenant isolation)."""
        ...

    async def create(self, tenant: Tenant) -> Tenant: ...

    async def update(self, tenant: Tenant) -> Tenant:
        """Persist every mutable field of ``tenant`` (name, status,
        metadata). Callers mutate the entity via its own domain methods
        (``activate()``, ``suspend()``, etc.) before calling this —
        the repository never contains transition logic itself."""
        ...

    async def list(
        self, *, offset: int, limit: int, status: TenantStatus | None = None
    ) -> tuple[list[Tenant], int]:
        """Return a page of tenants plus the total matching count, for
        the offset/limit back-office pagination pattern (Technical
        Architecture v2.0 SS5.7)."""
        ...
