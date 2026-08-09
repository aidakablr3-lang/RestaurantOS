"""MenuItem CRUD endpoints (Sprint 5 Step 4.8) plus the MenuItem<->
ModifierGroup attachment endpoint (Sprint 5 Step 4.9).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH``
``/api/v1/menu-categories/{id}/menu-items`` row, kept nested under
``menu_category_id`` throughout -- ``menu_category_id`` is scope (the
URL's own path parameter), never an editable body field, since
``MenuItem`` has no second, stable parent-scope column the way
``Table`` has ``branch_id`` alongside its movable ``table_zone_id``
(see ``update_menu_item.py``'s own docstring for the full reasoning).

``MenuItem`` has no branch dimension either (Architecture SS3.1 --
Restaurant-scoped like ``MenuCategory``), so every gate here is the
plain tenant-wide ``require_permission("menu.read"/"menu.manage")``,
identical to ``MenuCategoryRouter``'s own gates.

Every route resolves through a tenant-scoped repository lookup before
anything else -- a menu category, menu item, or modifier group that
exists but belongs to another tenant is a 404, identical to one that
does not exist at all, never a distinguishable 403 (no existence
leak).

Idempotency mirrors every other mutating router in this module: an
optional ``Idempotency-Key`` header on the three mutating routes
(create, update, replace-modifier-groups), opt-in, only the success
path cached.

``PUT /api/v1/menu-items/{id}/modifier-groups`` is a deliberately
*flat* path (Architecture SS7's own shape) -- no ``menu_category_id``
in the URL, the same flat-action pattern already established by
``POST /api/v1/tables/{id}/status``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuItemRequestDTO,
    MenuItemDTO,
    MenuItemModifierGroupsDTO,
    ReplaceMenuItemModifierGroupsRequestDTO,
    UpdateMenuItemRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateMenuItemUseCaseDep,
    GetMenuItemUseCaseDep,
    IdempotencyGuardDep,
    ListMenuItemsUseCaseDep,
    ReplaceMenuItemModifierGroupsUseCaseDep,
    RequireMenuManageDep,
    RequireMenuReadDep,
    UpdateMenuItemUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.menu_item_modifier_group_schemas import (
    MenuItemModifierGroupsResponseSchema,
    ReplaceMenuItemModifierGroupsRequestSchema,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.menu_item_schemas import (
    CreateMenuItemRequestSchema,
    MenuItemResponseSchema,
    UpdateMenuItemRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["menu-items"])

MenuCategoryIdPath = Annotated[str, Path(min_length=26, max_length=26)]
MenuItemIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _menu_item_to_schema(dto: MenuItemDTO) -> MenuItemResponseSchema:
    return MenuItemResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        menu_category_id=dto.menu_category_id,
        name=dto.name,
        price_amount=dto.price_amount,
        currency_code=dto.currency_code,
        is_available=dto.is_available,
        display_order=dto.display_order,
        recipe_id=dto.recipe_id,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/menu-categories/{menu_category_id}/menu-items",
    response_model=ApiResponse[MenuItemResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_item(
    menu_category_id: MenuCategoryIdPath,
    body: CreateMenuItemRequestSchema,
    principal: RequireMenuManageDep,
    use_case: CreateMenuItemUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateMenuItemRequestDTO(
                menu_category_id=menu_category_id,
                name=body.name,
                price_amount=body.price_amount,
                currency_code=body.currency_code,
                is_available=body.is_available,
                display_order=body.display_order,
            ),
        )
        response = ApiResponse(data=_menu_item_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"menuCategoryId": menu_category_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get(
    "/api/v1/menu-categories/{menu_category_id}/menu-items",
    response_model=ApiResponse[list[MenuItemResponseSchema]],
)
async def list_menu_items(
    menu_category_id: MenuCategoryIdPath,
    principal: RequireMenuReadDep,
    use_case: ListMenuItemsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[MenuItemResponseSchema]]:
    result = await use_case.execute(
        principal.tenant_id, menu_category_id, offset=offset, limit=limit
    )
    return ApiResponse(
        data=[_menu_item_to_schema(i) for i in result.menu_items],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/menu-categories/{menu_category_id}/menu-items/{menu_item_id}",
    response_model=ApiResponse[MenuItemResponseSchema],
)
async def get_menu_item(
    menu_category_id: MenuCategoryIdPath,
    menu_item_id: MenuItemIdPath,
    principal: RequireMenuReadDep,
    use_case: GetMenuItemUseCaseDep,
) -> ApiResponse[MenuItemResponseSchema]:
    result = await use_case.execute(principal.tenant_id, menu_category_id, menu_item_id)
    return ApiResponse(data=_menu_item_to_schema(result))


@router.patch(
    "/api/v1/menu-categories/{menu_category_id}/menu-items/{menu_item_id}",
    response_model=ApiResponse[MenuItemResponseSchema],
)
async def update_menu_item(
    menu_category_id: MenuCategoryIdPath,
    menu_item_id: MenuItemIdPath,
    body: UpdateMenuItemRequestSchema,
    principal: RequireMenuManageDep,
    use_case: UpdateMenuItemUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateMenuItemRequestDTO(
                menu_item_id=menu_item_id,
                menu_category_id=menu_category_id,
                name=body.name,
                price_amount=body.price_amount,
                currency_code=body.currency_code,
                is_available=body.is_available,
                display_order=body.display_order,
            ),
        )
        response = ApiResponse(data=_menu_item_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "menuCategoryId": menu_category_id,
                    "menuItemId": menu_item_id,
                    **body.model_dump(mode="json"),
                }
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


def _attachment_to_schema(dto: MenuItemModifierGroupsDTO) -> MenuItemModifierGroupsResponseSchema:
    return MenuItemModifierGroupsResponseSchema(
        menu_item_id=dto.menu_item_id,
        modifier_group_ids=sorted(dto.modifier_group_ids),
    )


@router.put(
    "/api/v1/menu-items/{menu_item_id}/modifier-groups",
    response_model=ApiResponse[MenuItemModifierGroupsResponseSchema],
)
async def replace_menu_item_modifier_groups(
    menu_item_id: MenuItemIdPath,
    body: ReplaceMenuItemModifierGroupsRequestSchema,
    principal: RequireMenuManageDep,
    use_case: ReplaceMenuItemModifierGroupsUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            ReplaceMenuItemModifierGroupsRequestDTO(
                menu_item_id=menu_item_id,
                modifier_group_ids=frozenset(body.modifier_group_ids),
            ),
        )
        response = ApiResponse(data=_attachment_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"menuItemId": menu_item_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
