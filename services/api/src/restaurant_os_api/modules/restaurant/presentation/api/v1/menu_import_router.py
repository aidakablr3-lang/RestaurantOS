"""Menu import endpoints: photo/PDF/CSV/XLSX -> extracted rows (review,
nothing persisted) -> commit (one transaction, persisted).

``restaurant_id`` is nested in both URLs for the same collection-shape
consistency every other menu route uses, but the extract route doesn't
actually look it up -- extraction is a pure file-in/rows-out operation
with no restaurant-scoped side effect to authorize beyond the coarse
``menu.manage`` gate (matching every other tenant-wide MenuCategory/
MenuItem route in this module). The commit route does resolve and use
it -- that's where a row's category actually gets created against a
real ``Restaurant``.

Both routes require ``menu.manage`` (not the read-only ``menu.read``) --
extraction costs real money per call and commit writes data, so neither
belongs to a read-only role.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, File, Header, Path, UploadFile, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.restaurant.application.dto import (
    CommitMenuImportRequestDTO,
    ExtractedMenuRowDTO,
    MenuImportCommitRowDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import UploadedMenuFile
from restaurant_os_api.modules.restaurant.presentation.dependencies import (
    CommitMenuImportUseCaseDep,
    ExtractMenuImportUseCaseDep,
    IdempotencyGuardDep,
    RequireMenuManageDep,
)
from restaurant_os_api.modules.restaurant.presentation.schemas.menu_import_schemas import (
    CommitMenuImportRequestSchema,
    CommitMenuImportResultResponseSchema,
    ExtractedMenuRowResponseSchema,
    MenuImportExtractResponseSchema,
)
from restaurant_os_api.platform.idempotency import fingerprint_request

router = APIRouter(tags=["menu-import"])

RestaurantIdPath = Annotated[str, Path(min_length=26, max_length=26)]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def _row_to_schema(dto: ExtractedMenuRowDTO) -> ExtractedMenuRowResponseSchema:
    return ExtractedMenuRowResponseSchema(
        category=dto.category,
        name=dto.name,
        raw_price=dto.raw_price,
        price_amount=dto.price_amount,
        confidence=dto.confidence.value,
        source_image_index=dto.source_image_index,
        dietary_type=dto.dietary_type,
        portion_label=dto.portion_label,
        pricing_unit=dto.pricing_unit,
        note=dto.note,
    )


@router.post(
    "/api/v1/restaurants/{restaurant_id}/menu-imports/extract",
    response_model=ApiResponse[MenuImportExtractResponseSchema],
)
async def extract_menu_import(
    restaurant_id: RestaurantIdPath,
    principal: RequireMenuManageDep,
    use_case: ExtractMenuImportUseCaseDep,
    files: Annotated[list[UploadFile], File()],
) -> ApiResponse[MenuImportExtractResponseSchema]:
    del restaurant_id  # URL-nested for route-shape consistency only; see module docstring
    del principal
    uploaded = [
        UploadedMenuFile(
            filename=f.filename or "upload",
            content_type=f.content_type or "application/octet-stream",
            data=await f.read(),
        )
        for f in files
    ]
    result = use_case.execute(uploaded)
    return ApiResponse(
        data=MenuImportExtractResponseSchema(rows=[_row_to_schema(r) for r in result.rows])
    )


@router.post(
    "/api/v1/restaurants/{restaurant_id}/menu-imports/commit",
    response_model=ApiResponse[CommitMenuImportResultResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def commit_menu_import(
    restaurant_id: RestaurantIdPath,
    body: CommitMenuImportRequestSchema,
    principal: RequireMenuManageDep,
    use_case: CommitMenuImportUseCaseDep,
    idempotency_guard: IdempotencyGuardDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> JSONResponse:
    async def execute() -> tuple[int, dict[str, Any]]:
        result = await use_case.execute(
            principal.tenant_id,
            CommitMenuImportRequestDTO(
                restaurant_id=restaurant_id,
                rows=[
                    MenuImportCommitRowDTO(
                        category=row.category,
                        name=row.name,
                        price_amount=row.price_amount,
                        portion_label=row.portion_label,
                    )
                    for row in body.rows
                ],
            ),
        )
        response = ApiResponse(
            data=CommitMenuImportResultResponseSchema(
                categories_created=result.categories_created, items_created=result.items_created
            )
        )
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
