from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import TableZoneDTO
from restaurant_os_api.modules.restaurant.domain.entities import TableZone


def table_zone_to_dto(table_zone: TableZone) -> TableZoneDTO:
    return TableZoneDTO(
        id=table_zone.id,
        tenant_id=table_zone.tenant_id,
        branch_id=table_zone.branch_id,
        name=table_zone.name,
        display_order=table_zone.display_order,
        created_at=table_zone.created_at,
    )
