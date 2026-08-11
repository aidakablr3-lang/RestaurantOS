from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import DiscountDTO
from restaurant_os_api.modules.operations.domain.entities import Discount


def discount_to_dto(discount: Discount) -> DiscountDTO:
    return DiscountDTO(
        id=discount.id,
        tenant_id=discount.tenant_id,
        name=discount.name,
        discount_type=discount.discount_type.value,
        value=discount.value,
        requires_approval=discount.requires_approval,
        created_at=discount.created_at,
        max_value=discount.max_value,
        active_from=discount.active_from,
        active_to=discount.active_to,
    )
