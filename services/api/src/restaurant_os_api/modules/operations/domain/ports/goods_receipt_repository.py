"""Repository port for GoodsReceipt."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import GoodsReceipt


class GoodsReceiptRepository(Protocol):
    async def create(self, goods_receipt: GoodsReceipt) -> GoodsReceipt: ...

    async def update(self, goods_receipt: GoodsReceipt) -> GoodsReceipt: ...
