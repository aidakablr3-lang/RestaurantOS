"""QR Code management endpoints (Sprint 5 Step 4.6).

Restaurant Platform Architecture SS7's ``POST``/``GET
/api/v1/tables/{id}/qr-codes`` rows -- both deliberately flat (no
``branch_id`` in the URL, unlike every other Table/TableZone route),
so both are gated the same way ``POST /api/v1/tables/{id}/status``
already is (Step 4.5): a coarse ``require_permission_at_any_scope``
gate here, plus the use case's own fine-grained
``resolve_and_authorize_branch`` call once the table (and therefore
its real ``branch_id``) is loaded.

The unauthenticated guest-resolution route
(``GET /api/v1/qr/{token}``) is explicitly **not** part of this
router -- deferred to a separate step per ADR 0001's own security
requirements (rate limiting, enumeration protection, abuse
monitoring), per the user's own Step 4.6/4.7 scope split.

Idempotency mirrors every other mutating router in this module: an
optional ``Idempotency-Key`` header on the one mutating route
(generate), opt-in, only the success path cached.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.restaurant.application.dto import QRCodeDTO
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CreateQRCodeUseCaseDep,
    IdempotencyGuardDep,
    ListQRCodesUseCaseDep,
    RequireTableManageAtAnyScopeDep,
    RequireTableReadAtAnyScopeDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.qr_code_schemas import (
    QRCodeResponseSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["qr-codes"])

TableIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _qr_code_to_schema(dto: QRCodeDTO) -> QRCodeResponseSchema:
    return QRCodeResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        table_id=dto.table_id,
        token=dto.token,
        status=dto.status,
        created_at=dto.created_at,
    )


@router.post(
    "/api/v1/tables/{table_id}/qr-codes",
    response_model=ApiResponse[QRCodeResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_qr_code(
    table_id: TableIdPath,
    principal: RequireTableManageAtAnyScopeDep,
    use_case: CreateQRCodeUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(principal.tenant_id, principal.user_id, table_id)
        response = ApiResponse(data=_qr_code_to_schema(result))
        return status.HTTP_201_CREATED, response.model_dump(mode="json", by_alias=True)

    if idempotency_key is None:
        http_status, response_body = await execute()
    else:
        http_status, response_body = await idempotency_guard.run(
            tenant_id=principal.tenant_id,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint_request({"tableId": table_id}),
            execute=execute,
        )
    return JSONResponse(status_code=http_status, content=response_body)


@router.get(
    "/api/v1/tables/{table_id}/qr-codes",
    response_model=ApiResponse[list[QRCodeResponseSchema]],
)
async def list_qr_codes(
    table_id: TableIdPath,
    principal: RequireTableReadAtAnyScopeDep,
    use_case: ListQRCodesUseCaseDep,
) -> ApiResponse[list[QRCodeResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, principal.user_id, table_id)
    return ApiResponse(data=[_qr_code_to_schema(c) for c in result])
