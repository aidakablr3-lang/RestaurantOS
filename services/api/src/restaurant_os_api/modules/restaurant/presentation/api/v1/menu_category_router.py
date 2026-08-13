"""MenuCategory CRUD endpoints (Sprint 5 Step 4.8).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH``
``/api/v1/restaurants/{restaurant_id}/menu-categories`` row, expanded
to the same explicit collection-vs-item route shape already used for
every other entity with a ``PATCH`` in that table: ``POST`` (create)
and ``GET`` (paginated list) against the collection path, ``GET``/
``PATCH /menu-categories/{id}`` against a single item -- kept nested
under ``restaurant_id`` throughout (rather than a flat
``/api/v1/menu-categories/{id}``), mirroring ``TableZoneRouter``'s own
``branch_id``-nested-throughout convention one level up.

``MenuCategory`` has no branch dimension (Architecture SS3.1 -- it
belongs to ``Restaurant``, deliberately not ``Branch``), so every gate
here is the plain tenant-wide ``require_permission("menu.read"/
"menu.manage")``, never ``require_branch_permission`` -- the same
shape ``RestaurantRouter``'s own gates use for the same reason.

Every route resolves through a tenant-scoped repository lookup before
anything else -- a restaurant or menu category that exists but belongs
to another tenant is a 404, identical to one that does not exist at
all, never a distinguishable 403 (no existence leak).

Idempotency mirrors every other mutating router in this module: an
optional ``Idempotency-Key`` header on the two mutating routes
(create, update), opt-in, only the success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuCategoryRequestDTO,
    MenuCategoryDTO,
    UpdateMenuCategoryRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateMenuCategoryUseCaseDep,
    GetMenuCategoryUseCaseDep,
    IdempotencyGuardDep,
    ListMenuCategoriesUseCaseDep,
    RequireMenuManageDep,
    RequireMenuReadDep,
    UpdateMenuCategoryUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.menu_category_schemas import (
    CreateMenuCategoryRequestSchema,
    MenuCategoryResponseSchema,
    UpdateMenuCategoryRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["menu-categories"])

RestaurantIdPath = Annotated[str, Path(min_length=26, max_length=26)]
MenuCategoryIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _menu_category_to_schema(dto: MenuCategoryDTO) -> MenuCategoryResponseSchema:
    return MenuCategoryResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        restaurant_id=dto.restaurant_id,
        name=dto.name,
        display_order=dto.display_order,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/restaurants/{restaurant_id}/menu-categories",
    response_model=ApiResponse[MenuCategoryResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_category(
    restaurant_id: RestaurantIdPath,
    body: CreateMenuCategoryRequestSchema,
    principal: RequireMenuManageDep,
    use_case: CreateMenuCategoryUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateMenuCategoryRequestDTO(
                restaurant_id=restaurant_id, name=body.name, display_order=body.display_order
            ),
        )
        response = ApiResponse(data=_menu_category_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"restaurantId": restaurant_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get(
    "/api/v1/restaurants/{restaurant_id}/menu-categories",
    response_model=ApiResponse[list[MenuCategoryResponseSchema]],
)
async def list_menu_categories(
    restaurant_id: RestaurantIdPath,
    principal: RequireMenuReadDep,
    use_case: ListMenuCategoriesUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[MenuCategoryResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, restaurant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_menu_category_to_schema(c) for c in result.menu_categories],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category_id}",
    response_model=ApiResponse[MenuCategoryResponseSchema],
)
async def get_menu_category(
    restaurant_id: RestaurantIdPath,
    menu_category_id: MenuCategoryIdPath,
    principal: RequireMenuReadDep,
    use_case: GetMenuCategoryUseCaseDep,
) -> ApiResponse[MenuCategoryResponseSchema]:
    result = await use_case.execute(principal.tenant_id, restaurant_id, menu_category_id)
    return ApiResponse(data=_menu_category_to_schema(result))


@router.patch(
    "/api/v1/restaurants/{restaurant_id}/menu-categories/{menu_category_id}",
    response_model=ApiResponse[MenuCategoryResponseSchema],
)
async def update_menu_category(
    restaurant_id: RestaurantIdPath,
    menu_category_id: MenuCategoryIdPath,
    body: UpdateMenuCategoryRequestSchema,
    principal: RequireMenuManageDep,
    use_case: UpdateMenuCategoryUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateMenuCategoryRequestDTO(
                menu_category_id=menu_category_id,
                restaurant_id=restaurant_id,
                name=body.name,
                display_order=body.display_order,
            ),
        )
        response = ApiResponse(data=_menu_category_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "restaurantId": restaurant_id,
                    "menuCategoryId": menu_category_id,
                    **body.model_dump(mode="json"),
                }
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
