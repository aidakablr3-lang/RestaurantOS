from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import MenuItemBranchPriceDTO
from restaurant_os_api.modules.restaurant.domain.entities import MenuItemBranchPrice


def menu_item_branch_price_to_dto(row: MenuItemBranchPrice) -> MenuItemBranchPriceDTO:
    return MenuItemBranchPriceDTO(
        id=row.id,
        tenant_id=row.tenant_id,
        branch_id=row.branch_id,
        menu_item_id=row.menu_item_id,
        price_amount=row.price_amount,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        created_at=row.created_at,
    )
