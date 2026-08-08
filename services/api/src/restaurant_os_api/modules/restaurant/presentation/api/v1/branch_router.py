"""Branch CRUD endpoints (Sprint 5 Step 4.2).

Restaurant Platform Architecture SS7's Branches row: ``POST
/api/v1/restaurants/{restaurant_id}/branches`` (nested -- a branch is
always created under a specific, already-tenant-verified restaurant),
``GET /api/v1/branches`` (flat, paginated, filtered to the caller's own
accessible branches per SS4.4/Step 4.0 Decision 2 -- not nested under
any one restaurant), ``GET``/``PATCH /api/v1/branches/{id}``, and the
two lifecycle actions ``POST /api/v1/branches/{id}/close`` /
``/reopen``, mirroring ``suspend``/``reactivate``'s existing
sub-resource-verb pattern. ``close_permanently()`` exists on the
domain entity but has no corresponding SS7 endpoint, so it is not
exposed here.

Every route resolves through a tenant-scoped repository lookup before
anything else -- a restaurant or branch that exists but belongs to
another tenant is a 404, identical to one that does not exist at all,
never a distinguishable 403 (no existence leak).

Idempotency mirrors ``restaurant_router.py`` exactly: an optional
``Idempotency-Key`` header on the four mutating routes, opt-in, only
the success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.restaurant.application.dto import (
    AddressRequestDTO,
    BranchDetailDTO,
    BranchDTO,
    CreateBranchRequestDTO,
    OperatingHoursEntryDTO,
    OperatingHoursEntryRequestDTO,
    ReplaceOperatingHoursRequestDTO,
    UpdateBranchRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CloseBranchUseCaseDep,
    CreateBranchUseCaseDep,
    GetBranchUseCaseDep,
    IdempotencyGuardDep,
    ListAccessibleBranchesUseCaseDep,
    ReopenBranchUseCaseDep,
    ReplaceOperatingHoursUseCaseDep,
    RequireBranchManageDep,
    RequireBranchManageTenantWideDep,
    RequireBranchReadAtAnyScopeDep,
    RequireBranchReadDep,
    UpdateBranchUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.branch_schemas import (
    AddressRequestSchema,
    AddressResponseSchema,
    BranchDetailResponseSchema,
    BranchResponseSchema,
    CreateBranchRequestSchema,
    UpdateBranchRequestSchema,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.operating_hours_schemas import (
    OperatingHoursEntryResponseSchema,
    ReplaceOperatingHoursRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["branches"])

RestaurantIdPath = Annotated[str, Path(min_length=26, max_length=26)]
BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _address_request_to_dto(schema: AddressRequestSchema | None) -> AddressRequestDTO | None:
    if schema is None:
        return None
    return AddressRequestDTO(
        line1=schema.line1,
        city=schema.city,
        country_code=schema.country_code,
        postal_code=schema.postal_code,
    )


def _branch_to_schema(dto: BranchDTO) -> BranchResponseSchema:
    return BranchResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        restaurant_id=dto.restaurant_id,
        name=dto.name,
        status=dto.status,
        address=(
            AddressResponseSchema(
                id=dto.address.id,
                line1=dto.address.line1,
                city=dto.address.city,
                country_code=dto.address.country_code,
                postal_code=dto.address.postal_code,
            )
            if dto.address is not None
            else None
        ),
        created_at=dto.created_at,
    )


def _operating_hours_entry_to_schema(
    dto: OperatingHoursEntryDTO,
) -> OperatingHoursEntryResponseSchema:
    return OperatingHoursEntryResponseSchema(
        id=dto.id,
        day_of_week=dto.day_of_week,
        is_closed=dto.is_closed,
        opens_at=dto.opens_at,
        closes_at=dto.closes_at,
    )


def _branch_detail_to_schema(dto: BranchDetailDTO) -> BranchDetailResponseSchema:
    return BranchDetailResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        restaurant_id=dto.restaurant_id,
        name=dto.name,
        status=dto.status,
        address=(
            AddressResponseSchema(
                id=dto.address.id,
                line1=dto.address.line1,
                city=dto.address.city,
                country_code=dto.address.country_code,
                postal_code=dto.address.postal_code,
            )
            if dto.address is not None
            else None
        ),
        created_at=dto.created_at,
        operating_hours=[_operating_hours_entry_to_schema(e) for e in dto.operating_hours],
    )


@router.post(
    "/api/v1/restaurants/{restaurant_id}/branches",
    response_model=ApiResponse[BranchResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_branch(
    restaurant_id: RestaurantIdPath,
    body: CreateBranchRequestSchema,
    principal: RequireBranchManageTenantWideDep,
    use_case: CreateBranchUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateBranchRequestDTO(
                restaurant_id=restaurant_id,
                name=body.name,
                address=_address_request_to_dto(body.address),
            ),
        )
        response = ApiResponse(data=_branch_to_schema(result))
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


@router.get("/api/v1/branches", response_model=ApiResponse[list[BranchResponseSchema]])
async def list_branches(
    principal: RequireBranchReadAtAnyScopeDep,
    use_case: ListAccessibleBranchesUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[BranchResponseSchema]]:
    branches, total = await use_case.execute(
        principal.tenant_id, principal.user_id, "branch.read", offset=offset, limit=limit
    )
    return ApiResponse(
        data=[
            _branch_to_schema(
                BranchDTO(
                    id=b.id,
                    tenant_id=b.tenant_id,
                    restaurant_id=b.restaurant_id,
                    name=b.name,
                    status=b.status.value,
                    address=None,
                    created_at=b.created_at,
                )
            )
            for b in branches
        ],
        meta=PaginationMeta(total=total, offset=offset, limit=limit),
    )


@router.get("/api/v1/branches/{branch_id}", response_model=ApiResponse[BranchDetailResponseSchema])
async def get_branch(
    branch_id: BranchIdPath,
    principal: RequireBranchReadDep,
    use_case: GetBranchUseCaseDep,
) -> ApiResponse[BranchDetailResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id)
    return ApiResponse(data=_branch_detail_to_schema(result))


@router.patch("/api/v1/branches/{branch_id}", response_model=ApiResponse[BranchResponseSchema])
async def update_branch(
    branch_id: BranchIdPath,
    body: UpdateBranchRequestSchema,
    principal: RequireBranchManageDep,
    use_case: UpdateBranchUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateBranchRequestDTO(
                branch_id=branch_id,
                name=body.name,
                address=_address_request_to_dto(body.address),
            ),
        )
        response = ApiResponse(data=_branch_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"branchId": branch_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post("/api/v1/branches/{branch_id}/close", response_model=ApiResponse[BranchResponseSchema])
async def close_branch(
    branch_id: BranchIdPath,
    principal: RequireBranchManageDep,
    use_case: CloseBranchUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(principal.tenant_id, branch_id)
        response = ApiResponse(data=_branch_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"branchId": branch_id}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.post(
    "/api/v1/branches/{branch_id}/reopen", response_model=ApiResponse[BranchResponseSchema]
)
async def reopen_branch(
    branch_id: BranchIdPath,
    principal: RequireBranchManageDep,
    use_case: ReopenBranchUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(principal.tenant_id, branch_id)
        response = ApiResponse(data=_branch_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"branchId": branch_id}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.put(
    "/api/v1/branches/{branch_id}/operating-hours",
    response_model=ApiResponse[list[OperatingHoursEntryResponseSchema]],
)
async def replace_operating_hours(
    branch_id: BranchIdPath,
    body: ReplaceOperatingHoursRequestSchema,
    principal: RequireBranchManageDep,
    use_case: ReplaceOperatingHoursUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            ReplaceOperatingHoursRequestDTO(
                branch_id=branch_id,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=e.day_of_week,
                        is_closed=e.is_closed,
                        opens_at=e.opens_at,
                        closes_at=e.closes_at,
                    )
                    for e in body.entries
                ],
            ),
        )
        response = ApiResponse(data=[_operating_hours_entry_to_schema(e) for e in result])
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {"branchId": branch_id, **body.model_dump(mode="json")}
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
