"""AddInventoryStep -- Phase 1 design doc §A.7, with one deliberate
scope expansion beyond the design doc's own text.

**Deviation, flagged explicitly:** §A.7 scoped ``add_inventory`` as
"registry node only... full step design (bulk parsing) is Phase 3, out
of scope." Per an explicit follow-up instruction overriding that
deferral, this step ships a real, single-item ``execute``/``verify``
(not a bulk importer -- "bulk parsing" and "one real inventory item per
step invocation" are different scopes; only the former is still
deferred).

**Second deviation, structural, required by the first:**
``CreateInventoryItemUseCase`` requires an existing
``inventory_category_id`` -- but no step in §A.7's table creates an
``InventoryCategory`` (Catalog's own category-equivalent,
``create_menu_category``, has no inventory counterpart in the graph).
Rather than collecting a category id the wizard has no earlier step to
have produced, this step's ``execute()`` calls **two** use cases in
sequence -- ``CreateInventoryCategoryUseCase`` then
``CreateInventoryItemUseCase`` -- the same "call more than one
existing use case from a single step" shape §A.7 already establishes
for ``create_manager``/``create_waiters``/``create_kitchen_staff``
(``CreateUserUseCase`` + ``AssignUserRoleUseCase``). No new business
logic is added; both calls are existing, unmodified use cases.

The acting user for both calls is ``ctx.owner_id`` -- the Owner holds
``inventory_food.manage`` by default (``tenant_provisioning_service.py``'s
own role catalogue), so this works for both ``category_type="food"``
and ``"beverage"`` without the wizard needing to reason about the
food/beverage permission gate at all.

``verify()`` reads the item back via ``GetInventoryItemUseCase`` --
gone or reassigned to a different branch is caught the same way
``GetTableUseCase`` catches a deleted table -- **and** independently
re-reads the item's own ``inventory_category_id`` (taken off the
just-read-back item, never off ``ctx`` -- see ``GetInventoryCategoryUseCase``
below) via the new ``GetInventoryCategoryUseCase``, since ``execute()``
writes *two* records (category, then item) and a ``verify()`` that only
re-checks the item would silently pass with the category gone --
``GetInventoryItemUseCase`` itself only touches the category for a
permission gate, never validates it still exists (confirmed by reading
its source: ``if category is not None and category.category_type is
FOOD: ...`` -- a ``None`` category just skips the gate silently).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.operations.application.dto import (
    CreateInventoryCategoryRequestDTO,
    CreateInventoryItemRequestDTO,
    InventoryItemDTO,
)
from restaurant_os_api.modules.operations.application.use_cases.create_inventory_category import (
    CreateInventoryCategoryUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.create_inventory_item import (
    CreateInventoryItemUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.get_inventory_category import (
    GetInventoryCategoryUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.get_inventory_item import (
    GetInventoryItemUseCase,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryCategoryNotFoundError,
    InventoryItemNotFoundError,
)


class AddInventoryStepInput(BaseModel):
    category_name: str
    category_type: Literal["food", "beverage"]
    item_name: str
    unit: str
    reorder_point: Decimal | None = None


class AddInventoryStep:
    def __init__(
        self,
        *,
        create_inventory_category_use_case: CreateInventoryCategoryUseCase,
        create_inventory_item_use_case: CreateInventoryItemUseCase,
        get_inventory_item_use_case: GetInventoryItemUseCase,
        get_inventory_category_use_case: GetInventoryCategoryUseCase,
    ) -> None:
        self.id = StepId.ADD_INVENTORY
        self.title = "Add inventory item"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_BRANCH,)
        self.collect_schema = AddInventoryStepInput
        self.autonomous = False

        self._create_inventory_category_use_case = create_inventory_category_use_case
        self._create_inventory_item_use_case = create_inventory_item_use_case
        self._get_inventory_item_use_case = get_inventory_item_use_case
        self._get_inventory_category_use_case = get_inventory_category_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: AddInventoryStepInput, ctx: OnboardingRunContext
    ) -> InventoryItemDTO:
        assert ctx.tenant_id is not None and ctx.owner_id is not None and ctx.branch_id is not None, (
            "add_inventory requires create_branch first"
        )
        category = await self._create_inventory_category_use_case.execute(
            ctx.tenant_id,
            ctx.owner_id,
            CreateInventoryCategoryRequestDTO(
                name=input.category_name, category_type=input.category_type
            ),
        )
        return await self._create_inventory_item_use_case.execute(
            ctx.tenant_id,
            ctx.owner_id,
            CreateInventoryItemRequestDTO(
                branch_id=ctx.branch_id,
                inventory_category_id=category.id,
                name=input.item_name,
                unit=input.unit,
                reorder_point=input.reorder_point,
            ),
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if (
            ctx.tenant_id is None
            or ctx.owner_id is None
            or ctx.branch_id is None
            or ctx.inventory_item_id is None
        ):
            return VerifyFailure(
                reason="tenant_id/owner_id/branch_id/inventory_item_id not yet in context"
            )
        try:
            item = await self._get_inventory_item_use_case.execute(
                ctx.tenant_id, ctx.owner_id, ctx.branch_id, ctx.inventory_item_id
            )
        except InventoryItemNotFoundError:
            return VerifyFailure(
                reason=f"inventory item {ctx.inventory_item_id} not found on read-back"
            )

        # item.inventory_category_id -- read off the just-fetched item,
        # never off ctx (ctx never carried it) -- so a mismatch between
        # what execute() actually wrote and what's stored now is itself
        # something this check would catch, not just a rubber stamp of
        # ctx's own memory of what happened.
        try:
            category = await self._get_inventory_category_use_case.execute(
                ctx.tenant_id, ctx.owner_id, item.inventory_category_id
            )
        except InventoryCategoryNotFoundError:
            return VerifyFailure(
                reason=(
                    f"inventory category {item.inventory_category_id} "
                    f"(item {item.id}'s own category) not found on read-back"
                )
            )

        return VerifySuccess(
            evidence=(
                f"GET inventory item {item.id} -> quantity_on_hand={item.quantity_on_hand}; "
                f"category {category.id} ('{category.name}') present"
            )
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "AddInventoryStep.undo() is not implemented in Phase 1 -- no caller abandons "
            "a run yet."
        )
