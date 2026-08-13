"""UpdateTableZoneUseCase.

Restaurant Platform Architecture SS7's ``PATCH /api/v1/branches/
{branch_id}/table-zones/{id}``. Both ``name`` and ``display_order``
are editable here in one call -- SS8's Dining Areas screen lists
"Create, edit, reorder" as one action set, and SS7 names no separate
reorder endpoint, so reordering *is* a ``PATCH`` that changes
``display_order``.

Same cross-branch scoping discipline as ``GetTableZoneUseCase``: a
table zone belonging to a different branch than the URL's own is
``TableZoneNotFoundError``, not a distinguishable error.

No domain event is published -- Architecture SS11's event catalogue
names only ``TableZoneCreated``, no ``TableZoneUpdated`` counterpart
(unlike ``Branch``/``Table``/``MenuItem``, which each get an explicit
Created+Updated pair), so none is invented here.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import (
    TableZoneDTO,
    UpdateTableZoneRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._table_zone_mapper import (
    table_zone_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    TableZoneNameConflictError,
    TableZoneNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import TableZoneRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateTableZoneUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        table_zone_repository_factory: Callable[[AsyncSession], TableZoneRepository],
    ) -> None:
        self._session_factory = session_factory
        self._table_zone_repository_factory = table_zone_repository_factory

    async def execute(self, tenant_id: str, request: UpdateTableZoneRequestDTO) -> TableZoneDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            table_zone_repo = self._table_zone_repository_factory(uow.session)

            table_zone = await table_zone_repo.get_by_id(tenant_id, request.table_zone_id)
            if table_zone is None or table_zone.branch_id != request.branch_id:
                raise TableZoneNotFoundError(request.table_zone_id)

            if request.name != table_zone.name:
                existing = await table_zone_repo.get_by_branch_id_and_name(
                    tenant_id, table_zone.branch_id, request.name
                )
                if existing is not None and existing.id != table_zone.id:
                    raise TableZoneNameConflictError(table_zone.branch_id, request.name)
                table_zone.name = request.name

            table_zone.display_order = request.display_order

            table_zone = await table_zone_repo.update(table_zone)

        return table_zone_to_dto(table_zone)
