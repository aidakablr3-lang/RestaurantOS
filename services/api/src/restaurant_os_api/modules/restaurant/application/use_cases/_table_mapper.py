from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import TableDTO
from restaurant_os_api.modules.restaurant.domain.entities import Table


def table_to_dto(table: Table) -> TableDTO:
    return TableDTO(
        id=table.id,
        tenant_id=table.tenant_id,
        branch_id=table.branch_id,
        table_zone_id=table.table_zone_id,
        table_number=table.table_number,
        capacity=table.capacity,
        status=table.status.value,
        created_at=table.created_at,
    )
