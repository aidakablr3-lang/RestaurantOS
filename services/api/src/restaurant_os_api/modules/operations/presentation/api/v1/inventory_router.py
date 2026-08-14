"""InventoryCategory + InventoryItem + StockMovement endpoints (Sprint 7
Step 5).

``inventory-categories`` are flat, tenant-wide (mirrors
``ModifierGroupRouter``'s own shape -- no FK parent). Creating one is
gated ``require_permission_at_any_scope("inventory.manage")`` --
*not* a strict tenant-wide requirement -- specifically so the default
"Inventory Manager" role (seeded branch-scoped only, per
``tenant_provisioning_service.py``) can manage the category taxonomy
its own branch's items belong to. A strict tenant-wide gate here made
that role's own `inventory.manage` grant unable to ever satisfy it,
since ``Role.default_scope`` is an authoring hint, not a structural
constraint (see ``role.py``), and the catalogue seeds this role
branch-scoped -- a real, previously-disclosed RBAC gap (Sprint 7
full-day operational simulation). Listing categories is gated the same
at-any-scope way for the identical reason (found and fixed 2026-08-14
alongside the food-vs-beverage split below -- the list route had been
left on the old strict tenant-wide gate even after create was fixed,
so the same branch-scoped Inventory Manager could create a category but
never see it in the list). ``inventory-items`` are branch-nested,
gated directly by ``require_branch_permission``. ``stock-movements`` is
flat (Architecture doc SS6: manual adjustments/waste logging;
``sale_deduction`` is never a direct client-facing POST) -- coarse
``require_permission_at_any_scope`` here, plus
``RecordStockMovementUseCase``'s/``ListStockMovementsUseCase``'s own
fine-grained ``resolve_and_authorize_branch`` call once the item's real
``branch_id`` is loaded, the same split every other flat Operations
route already follows.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.operations.application.dto import (
    CreateInventoryCategoryRequestDTO,
    CreateInventoryItemRequestDTO,
    InventoryCategoryDTO,
    InventoryItemDTO,
    RecordStockMovementRequestDTO,
    StockMovementDTO,
    UpdateInventoryItemRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    CreateInventoryCategoryUseCaseDep,
    CreateInventoryItemUseCaseDep,
    GetInventoryItemUseCaseDep,
    ListInventoryCategoriesUseCaseDep,
    ListInventoryItemsUseCaseDep,
    ListStockMovementsUseCaseDep,
    RecordStockMovementUseCaseDep,
    RequireInventoryManageAtAnyScopeDep,
    RequireInventoryManageDep,
    RequireInventoryReadAtAnyScopeDep,
    RequireInventoryReadDep,
    UpdateInventoryItemUseCaseDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.inventory_schemas import (
    CreateInventoryCategoryRequestSchema,
    CreateInventoryItemRequestSchema,
    InventoryCategoryResponseSchema,
    InventoryItemResponseSchema,
    RecordStockMovementRequestSchema,
    StockMovementResponseSchema,
    UpdateInventoryItemRequestSchema,
)

router = APIRouter(tags=["inventory"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
InventoryItemIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _category_to_schema(dto: InventoryCategoryDTO) -> InventoryCategoryResponseSchema:
    return InventoryCategoryResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        name=dto.name,
        category_type=dto.category_type,
        created_at=dto.created_at,
    )


def _item_to_schema(dto: InventoryItemDTO) -> InventoryItemResponseSchema:
    return InventoryItemResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        inventory_category_id=dto.inventory_category_id,
        name=dto.name,
        unit=dto.unit,
        quantity_on_hand=dto.quantity_on_hand,
        created_at=dto.created_at,
        reorder_point=dto.reorder_point,
        allow_negative_stock_override=dto.allow_negative_stock_override,
    )


def _movement_to_schema(dto: StockMovementDTO) -> StockMovementResponseSchema:
    return StockMovementResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        inventory_item_id=dto.inventory_item_id,
        movement_type=dto.movement_type,
        quantity_delta=dto.quantity_delta,
        occurred_at=dto.occurred_at,
        created_at=dto.created_at,
        reference_type=dto.reference_type,
        reference_id=dto.reference_id,
        idempotency_key=dto.idempotency_key,
    )


@router.post(
    "/api/v1/inventory-categories",
    response_model=ApiResponse[InventoryCategoryResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_category(
    body: CreateInventoryCategoryRequestSchema,
    principal: RequireInventoryManageAtAnyScopeDep,
    use_case: CreateInventoryCategoryUseCaseDep,
) -> ApiResponse[InventoryCategoryResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        CreateInventoryCategoryRequestDTO(name=body.name, category_type=body.category_type),
    )
    return ApiResponse(data=_category_to_schema(result))


@router.get(
    "/api/v1/inventory-categories",
    response_model=ApiResponse[list[InventoryCategoryResponseSchema]],
)
async def list_inventory_categories(
    principal: RequireInventoryReadAtAnyScopeDep,
    use_case: ListInventoryCategoriesUseCaseDep,
) -> ApiResponse[list[InventoryCategoryResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, principal.user_id)
    return ApiResponse(data=[_category_to_schema(c) for c in result.categories])


@router.post(
    "/api/v1/branches/{branch_id}/inventory-items",
    response_model=ApiResponse[InventoryItemResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_item(
    branch_id: BranchIdPath,
    body: CreateInventoryItemRequestSchema,
    principal: RequireInventoryManageDep,
    use_case: CreateInventoryItemUseCaseDep,
) -> ApiResponse[InventoryItemResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        CreateInventoryItemRequestDTO(
            branch_id=branch_id,
            inventory_category_id=body.inventory_category_id,
            name=body.name,
            unit=body.unit,
            reorder_point=body.reorder_point,
            allow_negative_stock_override=body.allow_negative_stock_override,
        ),
    )
    return ApiResponse(data=_item_to_schema(result))


@router.get(
    "/api/v1/branches/{branch_id}/inventory-items",
    response_model=ApiResponse[list[InventoryItemResponseSchema]],
)
async def list_inventory_items(
    branch_id: BranchIdPath,
    principal: RequireInventoryReadDep,
    use_case: ListInventoryItemsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[InventoryItemResponseSchema]]:
    result = await use_case.execute(
        principal.tenant_id, principal.user_id, branch_id, offset=offset, limit=limit
    )
    return ApiResponse(
        data=[_item_to_schema(i) for i in result.items],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/branches/{branch_id}/inventory-items/{inventory_item_id}",
    response_model=ApiResponse[InventoryItemResponseSchema],
)
async def get_inventory_item(
    branch_id: BranchIdPath,
    inventory_item_id: InventoryItemIdPath,
    principal: RequireInventoryReadDep,
    use_case: GetInventoryItemUseCaseDep,
) -> ApiResponse[InventoryItemResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id, principal.user_id, branch_id, inventory_item_id
    )
    return ApiResponse(data=_item_to_schema(result))


@router.patch(
    "/api/v1/branches/{branch_id}/inventory-items/{inventory_item_id}",
    response_model=ApiResponse[InventoryItemResponseSchema],
)
async def update_inventory_item(
    branch_id: BranchIdPath,
    inventory_item_id: InventoryItemIdPath,
    body: UpdateInventoryItemRequestSchema,
    principal: RequireInventoryManageDep,
    use_case: UpdateInventoryItemUseCaseDep,
) -> ApiResponse[InventoryItemResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        branch_id,
        UpdateInventoryItemRequestDTO(
            inventory_item_id=inventory_item_id,
            inventory_category_id=body.inventory_category_id,
            name=body.name,
            reorder_point=body.reorder_point,
            allow_negative_stock_override=body.allow_negative_stock_override,
        ),
    )
    return ApiResponse(data=_item_to_schema(result))


@router.post(
    "/api/v1/inventory-items/{inventory_item_id}/stock-movements",
    response_model=ApiResponse[StockMovementResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def record_stock_movement(
    inventory_item_id: InventoryItemIdPath,
    body: RecordStockMovementRequestSchema,
    principal: RequireInventoryManageAtAnyScopeDep,
    use_case: RecordStockMovementUseCaseDep,
) -> ApiResponse[StockMovementResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        RecordStockMovementRequestDTO(
            inventory_item_id=inventory_item_id,
            movement_type=body.movement_type,
            quantity_delta=body.quantity_delta,
            reason=body.reason,
            approved_by_user_id=body.approved_by_user_id,
            reference_type=body.reference_type,
            reference_id=body.reference_id,
        ),
    )
    return ApiResponse(data=_movement_to_schema(result))


@router.get(
    "/api/v1/inventory-items/{inventory_item_id}/stock-movements",
    response_model=ApiResponse[list[StockMovementResponseSchema]],
)
async def list_stock_movements(
    inventory_item_id: InventoryItemIdPath,
    principal: RequireInventoryReadAtAnyScopeDep,
    use_case: ListStockMovementsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[StockMovementResponseSchema]]:
    result = await use_case.execute(
        principal.tenant_id, principal.user_id, inventory_item_id, offset=offset, limit=limit
    )
    return ApiResponse(
        data=[_movement_to_schema(m) for m in result.movements],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )
