"""CreateMenuItemsStep -- Phase 1 design doc §A.7.

``CreateMenuItemUseCase`` creates one item per call; this step loops
it once per entry in ``input.items``, the same "collect many, call the
existing single-item use case per entry" shape as ``CreateTableStep``.
``requires=[create_menu_category]`` -- ``CreateMenuItemUseCase`` looks
up ``menu_category_repo.get_by_id``, a real dependency, not just a
spec assumption.

``verify()`` re-reads every id in ``ctx.menu_item_ids`` and fails if
any one is gone.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuItemRequestDTO,
    MenuItemDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_menu_item import (
    CreateMenuItemUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_menu_item import (
    GetMenuItemUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError


class MenuItemSpec(BaseModel):
    name: str
    price_amount: Decimal
    currency_code: str
    is_available: bool = True
    station: Literal["kitchen", "bar"] = "kitchen"


class CreateMenuItemsStepInput(BaseModel):
    items: list[MenuItemSpec] = Field(min_length=1)


class CreateMenuItemsStep:
    def __init__(
        self,
        *,
        create_menu_item_use_case: CreateMenuItemUseCase,
        get_menu_item_use_case: GetMenuItemUseCase,
    ) -> None:
        self.id = StepId.CREATE_MENU_ITEMS
        self.title = "Create menu items"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_MENU_CATEGORY,)
        self.collect_schema = CreateMenuItemsStepInput
        self.autonomous = False

        self._create_menu_item_use_case = create_menu_item_use_case
        self._get_menu_item_use_case = get_menu_item_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: CreateMenuItemsStepInput, ctx: OnboardingRunContext
    ) -> tuple[MenuItemDTO, ...]:
        assert ctx.tenant_id is not None and ctx.menu_category_id is not None, (
            "create_menu_items requires create_menu_category first"
        )
        created: list[MenuItemDTO] = []
        for spec in input.items:
            item = await self._create_menu_item_use_case.execute(
                ctx.tenant_id,
                CreateMenuItemRequestDTO(
                    menu_category_id=ctx.menu_category_id,
                    name=spec.name,
                    price_amount=spec.price_amount,
                    currency_code=spec.currency_code,
                    is_available=spec.is_available,
                    station=spec.station,
                ),
            )
            created.append(item)
        return tuple(created)

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.menu_category_id is None:
            return VerifyFailure(reason="tenant_id/menu_category_id not yet in context")
        if not ctx.menu_item_ids:
            return VerifyFailure(reason="no menu_item_ids recorded in context")

        verified: list[str] = []
        for item_id in ctx.menu_item_ids:
            try:
                item = await self._get_menu_item_use_case.execute(
                    ctx.tenant_id, ctx.menu_category_id, item_id
                )
            except MenuItemNotFoundError:
                return VerifyFailure(reason=f"menu item {item_id} not found on read-back")
            verified.append(item.id)

        return VerifySuccess(
            evidence=f"GET {len(verified)} menu item(s) -> all present: {verified}"
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateMenuItemsStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet."
        )
