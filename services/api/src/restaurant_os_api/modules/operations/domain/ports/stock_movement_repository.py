"""Repository port for StockMovement + StockAdjustment -- bundled the
same way ``PaymentRepository`` covers both Payment and Refund, since a
``StockAdjustment`` never exists without its linked ``StockMovement``."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import StockAdjustment, StockMovement


class StockMovementRepository(Protocol):
    async def create_movement(self, movement: StockMovement) -> StockMovement: ...

    async def list_for_item(
        self, tenant_id: str, inventory_item_id: str, *, offset: int, limit: int
    ) -> tuple[list[StockMovement], int]: ...

    async def create_adjustment(self, adjustment: StockAdjustment) -> StockAdjustment: ...
