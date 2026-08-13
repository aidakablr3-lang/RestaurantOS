from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import ModifierGroupDTO
from restaurant_os_api.modules.restaurant.domain.entities import ModifierGroup


def modifier_group_to_dto(modifier_group: ModifierGroup) -> ModifierGroupDTO:
    return ModifierGroupDTO(
        id=modifier_group.id,
        tenant_id=modifier_group.tenant_id,
        name=modifier_group.name,
        selection_type=modifier_group.selection_type.value,
        created_at=modifier_group.created_at,
    )
