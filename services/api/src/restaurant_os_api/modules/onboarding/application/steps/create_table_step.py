"""CreateTableStep -- Phase 1 design doc §A.7.

``CreateTableUseCase`` creates exactly one table per call. The wizard
step collects a whole dining area's tables in one form submission
(nobody wants to click "add table" fourteen separate times), so
``execute()`` loops the single-table use case once per entry in
``input.tables`` -- the same "collect many, call the existing
single-item use case per entry" shape ``GenerateQrCodesStep`` and the
staff-creation steps also use.

``verify()`` re-reads every table this step is responsible for (via
``ctx.table_ids``) and fails if *any one* of them is gone -- a step
that created five tables and lost one is not verified.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.restaurant.application.dto import CreateTableRequestDTO, TableDTO
from restaurant_os_api.modules.restaurant.application.use_cases.create_table import (
    CreateTableUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_table import GetTableUseCase
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError


class TableSpec(BaseModel):
    table_number: str
    capacity: int


class CreateTableStepInput(BaseModel):
    tables: list[TableSpec] = Field(min_length=1)


class CreateTableStep:
    def __init__(
        self,
        *,
        create_table_use_case: CreateTableUseCase,
        get_table_use_case: GetTableUseCase,
    ) -> None:
        self.id = StepId.CREATE_TABLE
        self.title = "Create tables"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_TABLE_ZONE,)
        self.collect_schema = CreateTableStepInput
        self.autonomous = False

        self._create_table_use_case = create_table_use_case
        self._get_table_use_case = get_table_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: CreateTableStepInput, ctx: OnboardingRunContext
    ) -> tuple[TableDTO, ...]:
        assert ctx.tenant_id is not None and ctx.branch_id is not None and ctx.table_zone_id is not None, (
            "create_table requires create_table_zone first"
        )
        created: list[TableDTO] = []
        for spec in input.tables:
            table = await self._create_table_use_case.execute(
                ctx.tenant_id,
                CreateTableRequestDTO(
                    branch_id=ctx.branch_id,
                    table_zone_id=ctx.table_zone_id,
                    table_number=spec.table_number,
                    capacity=spec.capacity,
                ),
            )
            created.append(table)
        return tuple(created)

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.branch_id is None:
            return VerifyFailure(reason="tenant_id/branch_id not yet in context")
        if not ctx.table_ids:
            return VerifyFailure(reason="no table_ids recorded in context")

        verified: list[str] = []
        for table_id in ctx.table_ids:
            try:
                table = await self._get_table_use_case.execute(
                    ctx.tenant_id, ctx.branch_id, table_id
                )
            except TableNotFoundError:
                return VerifyFailure(reason=f"table {table_id} not found on read-back")
            verified.append(table.id)

        return VerifySuccess(evidence=f"GET {len(verified)} table(s) -> all present: {verified}")

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateTableStep.undo() is not implemented in Phase 1 -- no caller abandons "
            "a run yet."
        )
