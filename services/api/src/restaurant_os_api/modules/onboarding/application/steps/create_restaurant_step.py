"""CreateRestaurantStep -- Phase 1 design doc §A.7.

Wraps ``CreateRestaurantUseCase``/``GetRestaurantUseCase`` exactly as
they already exist -- no new business logic. ``autofill`` offers the
tenant's own currency (set moments earlier by ``provision_tenant``,
already sitting in ``ctx``) as the restaurant's default, since a
restaurant almost always transacts in its tenant's currency and there
is no reason to make the operator retype it.
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
    CreateRestaurantRequestDTO,
    RestaurantDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_restaurant import (
    CreateRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_restaurant import (
    GetRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import RestaurantNotFoundError


class CreateRestaurantStepInput(BaseModel):
    legal_name: str
    display_name: str
    default_currency_code: str


class CreateRestaurantStep:
    def __init__(
        self,
        *,
        create_restaurant_use_case: CreateRestaurantUseCase,
        get_restaurant_use_case: GetRestaurantUseCase,
    ) -> None:
        self.id = StepId.CREATE_RESTAURANT
        self.title = "Create restaurant"
        self.requires: tuple[StepId, ...] = (StepId.PROVISION_TENANT,)
        self.collect_schema = CreateRestaurantStepInput
        self.autonomous = False

        self._create_restaurant_use_case = create_restaurant_use_case
        self._get_restaurant_use_case = get_restaurant_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        if ctx.expected_currency_code is not None:
            return {"default_currency_code": ctx.expected_currency_code}
        return {}

    async def execute(
        self, input: CreateRestaurantStepInput, ctx: OnboardingRunContext
    ) -> RestaurantDTO:
        assert ctx.tenant_id is not None, "create_restaurant requires provision_tenant first"
        return await self._create_restaurant_use_case.execute(
            ctx.tenant_id,
            CreateRestaurantRequestDTO(
                legal_name=input.legal_name,
                display_name=input.display_name,
                default_currency_code=input.default_currency_code,
            ),
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.restaurant_id is None:
            return VerifyFailure(reason="tenant_id/restaurant_id not yet in context")
        try:
            restaurant = await self._get_restaurant_use_case.execute(
                ctx.tenant_id, ctx.restaurant_id
            )
        except RestaurantNotFoundError:
            return VerifyFailure(reason=f"restaurant {ctx.restaurant_id} not found on read-back")
        if restaurant.status != "active":
            return VerifyFailure(
                reason=f"restaurant {ctx.restaurant_id} is '{restaurant.status}', not 'active'"
            )
        return VerifySuccess(
            evidence=f"GET restaurant {restaurant.id} -> status={restaurant.status}"
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateRestaurantStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet."
        )
