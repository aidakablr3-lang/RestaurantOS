"""CreateBranchStep -- Phase 1 design doc §A.7.

Wraps ``CreateBranchUseCase``/``GetBranchUseCase``. Address collection
is out of scope for Phase 1 (the wizard frontend that would collect a
rich address form is explicitly deferred, per the design doc's own
scope list) -- every branch this step creates starts with no address,
exactly as ``CreateBranchUseCase`` already supports (Restaurant
Platform Architecture SS3.1: "a Branch can exist with a placeholder
address during setup").
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
from restaurant_os_api.modules.restaurant.application.dto import BranchDTO, CreateBranchRequestDTO
from restaurant_os_api.modules.restaurant.application.use_cases.create_branch import (
    CreateBranchUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_branch import GetBranchUseCase
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError


class CreateBranchStepInput(BaseModel):
    name: str


class CreateBranchStep:
    def __init__(
        self,
        *,
        create_branch_use_case: CreateBranchUseCase,
        get_branch_use_case: GetBranchUseCase,
    ) -> None:
        self.id = StepId.CREATE_BRANCH
        self.title = "Create branch"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_RESTAURANT,)
        self.collect_schema = CreateBranchStepInput
        self.autonomous = False

        self._create_branch_use_case = create_branch_use_case
        self._get_branch_use_case = get_branch_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(self, input: CreateBranchStepInput, ctx: OnboardingRunContext) -> BranchDTO:
        assert ctx.tenant_id is not None and ctx.restaurant_id is not None, (
            "create_branch requires create_restaurant first"
        )
        return await self._create_branch_use_case.execute(
            ctx.tenant_id,
            CreateBranchRequestDTO(restaurant_id=ctx.restaurant_id, name=input.name, address=None),
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.branch_id is None:
            return VerifyFailure(reason="tenant_id/branch_id not yet in context")
        try:
            branch = await self._get_branch_use_case.execute(ctx.tenant_id, ctx.branch_id)
        except BranchNotFoundError:
            return VerifyFailure(reason=f"branch {ctx.branch_id} not found on read-back")
        if branch.status != "active":
            return VerifyFailure(
                reason=f"branch {ctx.branch_id} is '{branch.status}', not 'active'"
            )
        return VerifySuccess(evidence=f"GET branch {branch.id} -> status={branch.status}")

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateBranchStep.undo() is not implemented in Phase 1 -- no caller abandons a run yet."
        )
