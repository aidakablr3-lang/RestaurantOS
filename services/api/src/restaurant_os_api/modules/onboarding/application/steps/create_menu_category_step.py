"""CreateMenuCategoryStep -- Phase 1 design doc §A.7.

``requires=[create_restaurant]``, not ``create_branch`` -- per §A.7's
own amendment, ``CreateMenuCategoryUseCase`` looks up
``restaurant_repo.get_by_id(tenant_id, request.restaurant_id)``; menu
categories are restaurant-scoped, one level shallower than the data
model requires if gated behind a branch. Wraps
``CreateMenuCategoryUseCase``/``GetMenuCategoryUseCase`` directly, no
new business logic.
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
    CreateMenuCategoryRequestDTO,
    MenuCategoryDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_menu_category import (
    CreateMenuCategoryUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_menu_category import (
    GetMenuCategoryUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuCategoryNotFoundError


class CreateMenuCategoryStepInput(BaseModel):
    name: str
    display_order: int = 0


class CreateMenuCategoryStep:
    def __init__(
        self,
        *,
        create_menu_category_use_case: CreateMenuCategoryUseCase,
        get_menu_category_use_case: GetMenuCategoryUseCase,
    ) -> None:
        self.id = StepId.CREATE_MENU_CATEGORY
        self.title = "Create menu category"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_RESTAURANT,)
        self.collect_schema = CreateMenuCategoryStepInput
        self.autonomous = False

        self._create_menu_category_use_case = create_menu_category_use_case
        self._get_menu_category_use_case = get_menu_category_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: CreateMenuCategoryStepInput, ctx: OnboardingRunContext
    ) -> MenuCategoryDTO:
        assert ctx.tenant_id is not None and ctx.restaurant_id is not None, (
            "create_menu_category requires create_restaurant first"
        )
        return await self._create_menu_category_use_case.execute(
            ctx.tenant_id,
            CreateMenuCategoryRequestDTO(
                restaurant_id=ctx.restaurant_id,
                name=input.name,
                display_order=input.display_order,
            ),
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.restaurant_id is None or ctx.menu_category_id is None:
            return VerifyFailure(reason="tenant_id/restaurant_id/menu_category_id not yet in context")
        try:
            category = await self._get_menu_category_use_case.execute(
                ctx.tenant_id, ctx.restaurant_id, ctx.menu_category_id
            )
        except MenuCategoryNotFoundError:
            return VerifyFailure(
                reason=f"menu category {ctx.menu_category_id} not found on read-back"
            )
        return VerifySuccess(
            evidence=f"GET menu category {category.id} -> restaurant={category.restaurant_id}"
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateMenuCategoryStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet."
        )
