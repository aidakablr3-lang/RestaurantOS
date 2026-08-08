"""Restaurant CRUD endpoints (Sprint 5 Step 4.1).

Restaurant Platform Architecture SS7's Restaurants row: ``POST``/``GET
/api/v1/restaurants``, ``GET``/``PATCH /api/v1/restaurants/{id}``, plus
``POST /api/v1/restaurants/{id}/discontinue`` -- the lifecycle action,
mirroring ``POST /branches/{id}/close``'s own sub-resource-verb
pattern, since Restaurant has no hard-delete (SS3.1's
``created -> active -> discontinued`` status enum, not a DELETE verb).

``tenant_id`` never comes from the client -- every use case call below
passes ``principal.tenant_id`` (from the verified access token), never
anything out of the request body or path.

**Idempotency** (Step 4.0's ``IdempotencyGuard``, wired into a router
for the first time here): the three mutating routes accept an optional
``Idempotency-Key`` header. When present, the use case's outcome is
cached and replayed for a retried request carrying the same key and an
identical body; a reused key with a *different* body is rejected
(``IDEMPOTENCY_KEY_CONFLICT``). When absent, the route behaves exactly
like every other mutating route in this codebase -- idempotency is
opt-in per request, not mandatory. Only the *success* path is cached
here; a use case's own raised exception propagates normally through
the guard (which releases its claim) to the global exception handler,
so a failed attempt can simply be retried fresh rather than replaying
a stale error forever -- ``IdempotencyGuard`` itself supports caching
an error response too (see its own tests in Step 4.0), this router
just doesn't need that extra complexity for Restaurant CRUD.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateRestaurantRequestDTO,
    RestaurantDTO,
    UpdateRestaurantRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateRestaurantUseCaseDep,
    DiscontinueRestaurantUseCaseDep,
    GetRestaurantUseCaseDep,
    IdempotencyGuardDep,
    ListRestaurantsUseCaseDep,
    RequireRestaurantManageDep,
    RequireRestaurantReadDep,
    UpdateRestaurantUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.restaurant_schemas import (
    CreateRestaurantRequestSchema,
    RestaurantResponseSchema,
    UpdateRestaurantRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["restaurants"])

RestaurantIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _restaurant_to_schema(dto: RestaurantDTO) -> RestaurantResponseSchema:
    return RestaurantResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        legal_name=dto.legal_name,
        display_name=dto.display_name,
        default_currency_code=dto.default_currency_code,
        status=dto.status,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/restaurants",
    response_model=ApiResponse[RestaurantResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_restaurant(
    body: CreateRestaurantRequestSchema,
    principal: RequireRestaurantManageDep,
    use_case: CreateRestaurantUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateRestaurantRequestDTO(
                legal_name=body.legal_name,
                display_name=body.display_name,
                default_currency_code=body.default_currency_code,
            ),
        )
        response = ApiResponse(data=_restaurant_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(body.model_dump(mode="json")),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get("/api/v1/restaurants", response_model=ApiResponse[list[RestaurantResponseSchema]])
async def list_restaurants(
    principal: RequireRestaurantReadDep,
    use_case: ListRestaurantsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[RestaurantResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_restaurant_to_schema(r) for r in result.restaurants],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/restaurants/{restaurant_id}", response_model=ApiResponse[RestaurantResponseSchema]
)
async def get_restaurant(
    restaurant_id: RestaurantIdPath,
    principal: RequireRestaurantReadDep,
    use_case: GetRestaurantUseCaseDep,
) -> ApiResponse[RestaurantResponseSchema]:
    result = await use_case.execute(principal.tenant_id, restaurant_id)
    return ApiResponse(data=_restaurant_to_schema(result))


@router.patch(
    "/api/v1/restaurants/{restaurant_id}", response_model=ApiResponse[RestaurantResponseSchema]
)
async def update_restaurant(
    restaurant_id: RestaurantIdPath,
    body: UpdateRestaurantRequestSchema,
    principal: RequireRestaurantManageDep,
    use_case: UpdateRestaurantUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateRestaurantRequestDTO(
                restaurant_id=restaurant_id,
                legal_name=body.legal_name,
                display_name=body.display_name,
                default_currency_code=body.default_currency_code,
            ),
        )
        response = ApiResponse(data=_restaurant_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

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


@router.post(
    "/api/v1/restaurants/{restaurant_id}/discontinue",
    response_model=ApiResponse[RestaurantResponseSchema],
)
async def discontinue_restaurant(
    restaurant_id: RestaurantIdPath,
    principal: RequireRestaurantManageDep,
    use_case: DiscontinueRestaurantUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(principal.tenant_id, restaurant_id)
        response = ApiResponse(data=_restaurant_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"restaurantId": restaurant_id}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
