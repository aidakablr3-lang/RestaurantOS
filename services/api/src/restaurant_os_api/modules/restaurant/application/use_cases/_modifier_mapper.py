from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import ModifierDTO
from restaurant_os_api.modules.restaurant.domain.entities import Modifier


def modifier_to_dto(modifier: Modifier) -> ModifierDTO:
    return ModifierDTO(
        id=modifier.id,
        tenant_id=modifier.tenant_id,
        modifier_group_id=modifier.modifier_group_id,
        name=modifier.name,
        price_delta=modifier.price_delta,
        created_at=modifier.created_at,
    )
