"""CreateTableZoneStep -- Phase 1 design doc §A.7.

Wraps ``CreateTableZoneUseCase``/``GetTableZoneUseCase``. ``TableZone``
has no status/soft-delete column at all (unlike ``Branch``/``Restaurant``),
so ``verify()``'s "deleted out from under it" case is exactly
``TableZoneNotFoundError`` on read-back -- there is no active/inactive
state to additionally check.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateTableZoneRequestDTO,
    TableZoneDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_table_zone import (
    CreateTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_table_zone import (
    GetTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import TableZoneNotFoundError


class CreateTableZoneStepInput(BaseModel):
    name: str
    display_order: int = 0


class CreateTableZoneStep:
    def __init__(
        self,
        *,
        create_table_zone_use_case: CreateTableZoneUseCase,
        get_table_zone_use_case: GetTableZoneUseCase,
    ) -> None:
        self.id = StepId.CREATE_TABLE_ZONE
        self.title = "Create dining area"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_BRANCH,)
        self.collect_schema = CreateTableZoneStepInput
        self.autonomous = False

        self._create_table_zone_use_case = create_table_zone_use_case
        self._get_table_zone_use_case = get_table_zone_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: CreateTableZoneStepInput, ctx: OnboardingRunContext
    ) -> TableZoneDTO:
        assert ctx.tenant_id is not None and ctx.branch_id is not None, (
            "create_table_zone requires create_branch first"
        )
        return await self._create_table_zone_use_case.execute(
            ctx.tenant_id,
            CreateTableZoneRequestDTO(
                branch_id=ctx.branch_id, name=input.name, display_order=input.display_order
            ),
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.branch_id is None or ctx.table_zone_id is None:
            return VerifyFailure(reason="tenant_id/branch_id/table_zone_id not yet in context")
        try:
            table_zone = await self._get_table_zone_use_case.execute(
                ctx.tenant_id, ctx.branch_id, ctx.table_zone_id
            )
        except TableZoneNotFoundError:
            return VerifyFailure(reason=f"table zone {ctx.table_zone_id} not found on read-back")
        return VerifySuccess(
            evidence=f"GET table zone {table_zone.id} -> branch={table_zone.branch_id}"
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateTableZoneStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet."
        )
