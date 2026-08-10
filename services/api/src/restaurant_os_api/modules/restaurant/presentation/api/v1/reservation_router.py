"""Reservation CRUD endpoints (Sprint 5 Step 4.11) -- the final
implementation step required to complete the currently-defined
Restaurant Platform backend (Architecture SS7/SS14/SS15).

Restaurant Platform Architecture SS7's ``POST``/``GET``/``PATCH``
``/api/v1/branches/{branch_id}/reservations`` row -- foundation CRUD
only, no waitlist logic. Every route is nested under ``branch_id``,
the same shape ``TableRouter``'s own CRUD routes use, so every gate
here is the plain ``require_branch_permission("reservation.manage"/
"reservation.read")`` -- Reservation gets no separate flat
status-change route the way Table does, so ``PATCH`` alone carries
both plain field edits and status transitions (see
``UpdateReservationUseCase``'s own docstring for how a transition is
never assigned directly).

Every route resolves through a tenant-scoped repository lookup before
anything else -- a branch, table, or reservation that exists but
belongs to another tenant (or, for a single reservation, a different
branch) is a 404, identical to one that does not exist at all, never a
distinguishable 403 (no existence leak).

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
    CreateReservationRequestDTO,
    ReservationDTO,
    UpdateReservationRequestDTO,
)
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateReservationUseCaseDep,
    GetReservationUseCaseDep,
    IdempotencyGuardDep,
    ListReservationsUseCaseDep,
    RequireReservationManageDep,
    RequireReservationReadDep,
    UpdateReservationUseCaseDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.reservation_schemas import (
    CreateReservationRequestSchema,
    ReservationResponseSchema,
    UpdateReservationRequestSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["reservations"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
ReservationIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _reservation_to_schema(dto: ReservationDTO) -> ReservationResponseSchema:
    return ReservationResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        table_id=dto.table_id,
        customer_id=dto.customer_id,
        party_size=dto.party_size,
        requested_at=dto.requested_at,
        status=dto.status,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/branches/{branch_id}/reservations",
    response_model=ApiResponse[ReservationResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    branch_id: BranchIdPath,
    body: CreateReservationRequestSchema,
    principal: RequireReservationManageDep,
    use_case: CreateReservationUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CreateReservationRequestDTO(
                branch_id=branch_id,
                party_size=body.party_size,
                requested_at=body.requested_at,
                table_id=body.table_id,
            ),
        )
        response = ApiResponse(data=_reservation_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

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


@router.get(
    "/api/v1/branches/{branch_id}/reservations",
    response_model=ApiResponse[list[ReservationResponseSchema]],
)
async def list_reservations(
    branch_id: BranchIdPath,
    principal: RequireReservationReadDep,
    use_case: ListReservationsUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[ReservationResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, branch_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_reservation_to_schema(r) for r in result.reservations],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/branches/{branch_id}/reservations/{reservation_id}",
    response_model=ApiResponse[ReservationResponseSchema],
)
async def get_reservation(
    branch_id: BranchIdPath,
    reservation_id: ReservationIdPath,
    principal: RequireReservationReadDep,
    use_case: GetReservationUseCaseDep,
) -> ApiResponse[ReservationResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id, reservation_id)
    return ApiResponse(data=_reservation_to_schema(result))


@router.patch(
    "/api/v1/branches/{branch_id}/reservations/{reservation_id}",
    response_model=ApiResponse[ReservationResponseSchema],
)
async def update_reservation(
    branch_id: BranchIdPath,
    reservation_id: ReservationIdPath,
    body: UpdateReservationRequestSchema,
    principal: RequireReservationManageDep,
    use_case: UpdateReservationUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            UpdateReservationRequestDTO(
                reservation_id=reservation_id,
                branch_id=branch_id,
                party_size=body.party_size,
                status=body.status.value,
                table_id=body.table_id,
            ),
        )
        response = ApiResponse(data=_reservation_to_schema(result))
        return status.HTTP_200_OK, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request(
                {
                    "branchId": branch_id,
                    "reservationId": reservation_id,
                    **body.model_dump(mode="json"),
                }
            ),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)
