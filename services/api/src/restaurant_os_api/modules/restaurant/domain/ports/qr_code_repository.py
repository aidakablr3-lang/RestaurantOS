"""Repository port for QRCode."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.restaurant.domain.entities import QRCode


class QRCodeRepository(Protocol):
    async def get_by_id(self, tenant_id: str, qr_code_id: str) -> QRCode | None: ...

    async def get_by_token(self, token: str) -> QRCode | None:
        """Global lookup by opaque token, **not** tenant-scoped -- the
        unauthenticated guest-resolution path (Restaurant Platform
        Architecture SS3.1) looks up by token alone, before tenant
        context is known; the token itself is what establishes it."""
        ...

    async def create(self, qr_code: QRCode) -> QRCode: ...

    async def update(self, qr_code: QRCode) -> QRCode: ...

    async def list_for_table(self, tenant_id: str, table_id: str) -> list[QRCode]:
        """Full regeneration history, newest first."""
        ...
