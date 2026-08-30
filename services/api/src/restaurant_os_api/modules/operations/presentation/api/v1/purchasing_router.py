"""Supplier + PurchaseOrder + PurchaseOrderItem + GoodsReceipt endpoints
(Sprint 7 Step 6).

``suppliers`` are flat, tenant-wide (mirrors ``ModifierGroupRouter``'s
own shape). ``purchase-orders`` are branch-nested for create/list/get;
``items``/``send``/``cancel``/``receipts`` are flat (Architecture doc
SS6's own representative list only shows POST/GET/PATCH for
purchase-orders and a receipts POST -- this router instead uses
dedicated action routes for the status graph, matching the
Order/Bill/CashDrawer precedent already established every other place
this codebase has a real workflow to guard, rather than a generic
PATCH with no non-status field worth editing).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status
from fastapi.responses import JSONResponse

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.operations.application.dto import (
    AddPurchaseOrderItemRequestDTO,
    ConfirmGoodsReceiptLineRequestDTO,
    ConfirmGoodsReceiptRequestDTO,
    CreatePurchaseOrderRequestDTO,
    CreateSupplierRequestDTO,
    GoodsReceiptDTO,
    PurchaseOrderDTO,
    SupplierDTO,
    UpdateSupplierRequestDTO,
)
from restaurant_os_api.modules.operations.presentation.dependencies import (
    AddPurchaseOrderItemUseCaseDep,
    CancelPurchaseOrderUseCaseDep,
    ConfirmGoodsReceiptUseCaseDep,
    CreatePurchaseOrderUseCaseDep,
    CreateSupplierUseCaseDep,
    GetPurchaseOrderUseCaseDep,
    ListPurchaseOrdersUseCaseDep,
    ListSuppliersUseCaseDep,
    RequirePurchasingManageAtAnyScopeDep,
    RequirePurchasingManageDep,
    RequirePurchasingManageTenantWideDep,
    RequirePurchasingReadDep,
    RequirePurchasingReadTenantWideDep,
    SendPurchaseOrderUseCaseDep,
    UpdateSupplierUseCaseDep,
)
from restaurant_os_api.modules.operations.presentation.schemas.purchasing_schemas import (
    AddPurchaseOrderItemRequestSchema,
    ConfirmGoodsReceiptRequestSchema,
    CreatePurchaseOrderRequestSchema,
    CreateSupplierRequestSchema,
    GoodsReceiptResponseSchema,
    PurchaseOrderItemResponseSchema,
    PurchaseOrderResponseSchema,
    SupplierResponseSchema,
    UpdateSupplierRequestSchema,
)
from restaurant_os_api.modules.restaurant.application.dto import AddressRequestDTO
from restaurant_os_api.modules.restaurant.presentation.schemas.branch_schemas import (
    AddressRequestSchema,
    AddressResponseSchema,
)

router = APIRouter(tags=["purchasing"])

BranchIdPath = Annotated[str, Path(min_length=26, max_length=26)]
SupplierIdPath = Annotated[str, Path(min_length=26, max_length=26)]
PurchaseOrderIdPath = Annotated[str, Path(min_length=26, max_length=26)]


def _address_request_to_dto(schema: AddressRequestSchema | None) -> AddressRequestDTO | None:
    if schema is None:
        return None
    return AddressRequestDTO(
        line1=schema.line1,
        city=schema.city,
        state=schema.state,
        country_code=schema.country_code,
        postal_code=schema.postal_code,
    )


def _supplier_to_schema(dto: SupplierDTO) -> SupplierResponseSchema:
    return SupplierResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        name=dto.name,
        status=dto.status,
        created_at=dto.created_at,
        address=(
            AddressResponseSchema(
                id=dto.address.id,
                line1=dto.address.line1,
                city=dto.address.city,
                state=dto.address.state,
                country_code=dto.address.country_code,
                postal_code=dto.address.postal_code,
            )
            if dto.address is not None
            else None
        ),
    )


def _purchase_order_to_schema(dto: PurchaseOrderDTO) -> PurchaseOrderResponseSchema:
    return PurchaseOrderResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        branch_id=dto.branch_id,
        supplier_id=dto.supplier_id,
        status=dto.status,
        created_at=dto.created_at,
        items=[
            PurchaseOrderItemResponseSchema(
                id=i.id,
                purchase_order_id=i.purchase_order_id,
                inventory_item_id=i.inventory_item_id,
                quantity_ordered=i.quantity_ordered,
                quantity_received=i.quantity_received,
                created_at=i.created_at,
            )
            for i in dto.items
        ],
    )


def _goods_receipt_to_schema(dto: GoodsReceiptDTO) -> GoodsReceiptResponseSchema:
    return GoodsReceiptResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        purchase_order_id=dto.purchase_order_id,
        status=dto.status,
        received_at=dto.received_at,
        created_at=dto.created_at,
        has_discrepancy=dto.has_discrepancy,
        purchase_order=_purchase_order_to_schema(dto.purchase_order),
    )


@router.post(
    "/api/v1/suppliers",
    response_model=ApiResponse[SupplierResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    body: CreateSupplierRequestSchema,
    principal: RequirePurchasingManageTenantWideDep,
    use_case: CreateSupplierUseCaseDep,
) -> ApiResponse[SupplierResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        CreateSupplierRequestDTO(name=body.name, address=_address_request_to_dto(body.address)),
    )
    return ApiResponse(data=_supplier_to_schema(result))


@router.get("/api/v1/suppliers", response_model=ApiResponse[list[SupplierResponseSchema]])
async def list_suppliers(
    principal: RequirePurchasingReadTenantWideDep,
    use_case: ListSuppliersUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[SupplierResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_supplier_to_schema(s) for s in result.suppliers],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.patch("/api/v1/suppliers/{supplier_id}", response_model=ApiResponse[SupplierResponseSchema])
async def update_supplier(
    supplier_id: SupplierIdPath,
    body: UpdateSupplierRequestSchema,
    principal: RequirePurchasingManageTenantWideDep,
    use_case: UpdateSupplierUseCaseDep,
) -> ApiResponse[SupplierResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        UpdateSupplierRequestDTO(
            supplier_id=supplier_id,
            name=body.name,
            status=body.status,
            address=_address_request_to_dto(body.address),
        ),
    )
    return ApiResponse(data=_supplier_to_schema(result))


@router.post(
    "/api/v1/branches/{branch_id}/purchase-orders",
    response_model=ApiResponse[PurchaseOrderResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    branch_id: BranchIdPath,
    body: CreatePurchaseOrderRequestSchema,
    principal: RequirePurchasingManageDep,
    use_case: CreatePurchaseOrderUseCaseDep,
) -> ApiResponse[PurchaseOrderResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        CreatePurchaseOrderRequestDTO(branch_id=branch_id, supplier_id=body.supplier_id),
    )
    return ApiResponse(data=_purchase_order_to_schema(result))


@router.get(
    "/api/v1/branches/{branch_id}/purchase-orders",
    response_model=ApiResponse[list[PurchaseOrderResponseSchema]],
)
async def list_purchase_orders(
    branch_id: BranchIdPath,
    principal: RequirePurchasingReadDep,
    use_case: ListPurchaseOrdersUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[PurchaseOrderResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, branch_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_purchase_order_to_schema(po) for po in result.purchase_orders],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get(
    "/api/v1/branches/{branch_id}/purchase-orders/{purchase_order_id}",
    response_model=ApiResponse[PurchaseOrderResponseSchema],
)
async def get_purchase_order(
    branch_id: BranchIdPath,
    purchase_order_id: PurchaseOrderIdPath,
    principal: RequirePurchasingReadDep,
    use_case: GetPurchaseOrderUseCaseDep,
) -> ApiResponse[PurchaseOrderResponseSchema]:
    result = await use_case.execute(principal.tenant_id, branch_id, purchase_order_id)
    return ApiResponse(data=_purchase_order_to_schema(result))


@router.post(
    "/api/v1/purchase-orders/{purchase_order_id}/items",
    response_model=ApiResponse[PurchaseOrderResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def add_purchase_order_item(
    purchase_order_id: PurchaseOrderIdPath,
    body: AddPurchaseOrderItemRequestSchema,
    principal: RequirePurchasingManageAtAnyScopeDep,
    use_case: AddPurchaseOrderItemUseCaseDep,
) -> ApiResponse[PurchaseOrderResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        AddPurchaseOrderItemRequestDTO(
            purchase_order_id=purchase_order_id,
            inventory_item_id=body.inventory_item_id,
            quantity_ordered=body.quantity_ordered,
        ),
    )
    return ApiResponse(data=_purchase_order_to_schema(result))


@router.post(
    "/api/v1/purchase-orders/{purchase_order_id}/send",
    response_model=ApiResponse[PurchaseOrderResponseSchema],
)
async def send_purchase_order(
    purchase_order_id: PurchaseOrderIdPath,
    principal: RequirePurchasingManageAtAnyScopeDep,
    use_case: SendPurchaseOrderUseCaseDep,
) -> ApiResponse[PurchaseOrderResponseSchema]:
    result = await use_case.execute(principal.tenant_id, principal.user_id, purchase_order_id)
    return ApiResponse(data=_purchase_order_to_schema(result))


@router.post(
    "/api/v1/purchase-orders/{purchase_order_id}/cancel",
    response_model=ApiResponse[PurchaseOrderResponseSchema],
)
async def cancel_purchase_order(
    purchase_order_id: PurchaseOrderIdPath,
    principal: RequirePurchasingManageAtAnyScopeDep,
    use_case: CancelPurchaseOrderUseCaseDep,
) -> ApiResponse[PurchaseOrderResponseSchema]:
    result = await use_case.execute(principal.tenant_id, principal.user_id, purchase_order_id)
    return ApiResponse(data=_purchase_order_to_schema(result))


@router.post(
    "/api/v1/purchase-orders/{purchase_order_id}/receipts",
    response_model=ApiResponse[GoodsReceiptResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def confirm_goods_receipt(
    purchase_order_id: PurchaseOrderIdPath,
    body: ConfirmGoodsReceiptRequestSchema,
    principal: RequirePurchasingManageAtAnyScopeDep,
    use_case: ConfirmGoodsReceiptUseCaseDep,
) -> JSONResponse:
    result = await use_case.execute(
        principal.tenant_id,
        principal.user_id,
        ConfirmGoodsReceiptRequestDTO(
            purchase_order_id=purchase_order_id,
            lines=[
                ConfirmGoodsReceiptLineRequestDTO(
                    purchase_order_item_id=line.purchase_order_item_id,
                    quantity_received=line.quantity_received,
                )
                for line in body.lines
            ],
        ),
    )
    response: ApiResponse[GoodsReceiptResponseSchema] = ApiResponse(
        data=_goods_receipt_to_schema(result)
    )
    body_dict: dict[str, Any] = response.model_dump(mode="json", by_alias=True)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content=body_dict)
