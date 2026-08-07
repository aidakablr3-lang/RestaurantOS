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
        attempting an insert.

        Correction from this port's first draft: this is an
        application-level check only — the migration deliberately does
        not add a database-level unique constraint on ``legal_name``,
        since two distinct, legitimately-named businesses coinciding is
        plausible and not something the schema should hard-block. If
        this check ever needs to be race-proof, that's a real,
        separate design decision (e.g., an advisory lock around
        onboarding), not something to bolt on silently.
        """
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
