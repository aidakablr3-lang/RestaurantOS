from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import TabDTO
from restaurant_os_api.modules.operations.domain.entities import Tab


def tab_to_dto(tab: Tab) -> TabDTO:
    return TabDTO(
        id=tab.id,
        tenant_id=tab.tenant_id,
        branch_id=tab.branch_id,
        status=tab.status.value,
        opened_at=tab.opened_at,
        created_at=tab.created_at,
        table_id=tab.table_id,
        customer_id=tab.customer_id,
        closed_at=tab.closed_at,
    )
