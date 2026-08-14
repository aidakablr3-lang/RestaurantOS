"""Dependency providers wiring concrete Infrastructure to the operations
module's Application ports (Sprint 7 Step 3, Order + Kitchen slice).

Mirrors ``modules.restaurant.presentation.dependencies``'s exact
convention. Authentication, permission-gating, and the session factory
are cross-cutting, already-built pieces, imported directly from
identity's own dependencies module. Branch/Restaurant/Table/MenuItem/
MenuCategory repositories are reused directly from the restaurant
module -- Operations doesn't own those tables and has no reason to
duplicate their repository implementations.

**Order/Tab authorization shape:** create routes are branch-nested
(``require_branch_permission``); ``items``/``fire``/``close``/``void``
and Tab's own ``close`` are flat (no ``branch_id`` in the URL), so they
use the coarse ``require_permission_at_any_scope`` gate here plus each
use case's own fine-grained ``resolve_and_authorize_branch`` call --
the exact "coarse router gate, fine-grained use-case decision" split
``ChangeTableStatusUseCase`` established in the restaurant module.
Kitchen's two status routes follow the identical shape.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from restaurant_os_api.modules.identity.application.dto import AuthenticatedPrincipalDTO
from restaurant_os_api.modules.identity.presentation.dependencies import (
    ResolveUserPermissionsUseCaseDep,
    SessionFactoryDep,
    require_branch_permission,
    require_permission,
    require_permission_at_any_scope,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    AddOrderItemUseCase,
    AddPurchaseOrderItemUseCase,
    ApplyBillAdjustmentUseCase,
    CancelPurchaseOrderUseCase,
    CloseCashDrawerUseCase,
    CloseOrderUseCase,
    CloseTabUseCase,
    ConfirmGoodsReceiptUseCase,
    CreateDiscountUseCase,
    CreateInventoryCategoryUseCase,
    CreateInventoryItemUseCase,
    CreateOrderUseCase,
    CreatePurchaseOrderUseCase,
    CreateSupplierUseCase,
    CreateTabUseCase,
    CreateTaxUseCase,
    FireOrderUseCase,
    GenerateBillUseCase,
    GetBillUseCase,
    GetEndOfDayReportUseCase,
    GetInventoryItemUseCase,
    GetMenuItemRecipeUseCase,
    GetOpenCashDrawerUseCase,
    GetOrderUseCase,
    GetPurchaseOrderUseCase,
    GuestAddOrderItemUseCase,
    GuestGetOrderUseCase,
    GuestSubmitOrderUseCase,
    ListDiscountsUseCase,
    ListInventoryCategoriesUseCase,
    ListInventoryItemsUseCase,
    ListKitchenTicketsUseCase,
    ListOrdersUseCase,
    ListPaymentsUseCase,
    ListPurchaseOrdersUseCase,
    ListStockMovementsUseCase,
    ListSuppliersUseCase,
    ListTaxesUseCase,
    OpenCashDrawerUseCase,
    RecordPaymentUseCase,
    RecordStockMovementUseCase,
    RequestRefundUseCase,
    ReviseRecipeUseCase,
    SendPurchaseOrderUseCase,
    UpdateInventoryItemUseCase,
    UpdateKitchenItemStatusUseCase,
    UpdateKitchenTicketStatusUseCase,
    UpdateSupplierUseCase,
    VoidOrderItemUseCase,
    VoidOrderUseCase,
)
from restaurant_os_api.modules.operations.infrastructure.database.repositories import (
    SQLAlchemyBillRepository,
    SQLAlchemyCashDrawerRepository,
    SQLAlchemyDiscountRepository,
    SQLAlchemyGoodsReceiptRepository,
    SQLAlchemyInventoryCategoryRepository,
    SQLAlchemyInventoryItemRepository,
    SQLAlchemyKitchenTicketRepository,
    SQLAlchemyLedgerRepository,
    SQLAlchemyOrderRepository,
    SQLAlchemyPaymentRepository,
    SQLAlchemyPurchaseOrderRepository,
    SQLAlchemyRecipeRepository,
    SQLAlchemyStockMovementRepository,
    SQLAlchemySupplierRepository,
    SQLAlchemyTabRepository,
    SQLAlchemyTaxRepository,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyAddressRepository,
    SQLAlchemyBranchRepository,
    SQLAlchemyMenuCategoryRepository,
    SQLAlchemyMenuItemRepository,
    SQLAlchemyRestaurantRepository,
    SQLAlchemyTableRepository,
)
from restaurant_os_api.platform.idempotency import IdempotencyGuard
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter

__all__ = [
    "AddOrderItemUseCaseDep",
    "AddPurchaseOrderItemUseCaseDep",
    "ApplyBillAdjustmentUseCaseDep",
    "CancelPurchaseOrderUseCaseDep",
    "CloseCashDrawerUseCaseDep",
    "CloseOrderUseCaseDep",
    "CloseTabUseCaseDep",
    "ConfirmGoodsReceiptUseCaseDep",
    "CreateDiscountUseCaseDep",
    "CreateInventoryCategoryUseCaseDep",
    "CreateInventoryItemUseCaseDep",
    "CreateOrderUseCaseDep",
    "CreatePurchaseOrderUseCaseDep",
    "CreateSupplierUseCaseDep",
    "CreateTabUseCaseDep",
    "CreateTaxUseCaseDep",
    "FireOrderUseCaseDep",
    "GenerateBillUseCaseDep",
    "GetBillUseCaseDep",
    "GetEndOfDayReportUseCaseDep",
    "GetInventoryItemUseCaseDep",
    "GetMenuItemRecipeUseCaseDep",
    "GetOpenCashDrawerUseCaseDep",
    "GetOrderUseCaseDep",
    "GetPurchaseOrderUseCaseDep",
    "GuestAddOrderItemUseCaseDep",
    "GuestGetOrderUseCaseDep",
    "GuestSubmitOrderUseCaseDep",
    "IdempotencyGuardDep",
    "ListDiscountsUseCaseDep",
    "ListInventoryCategoriesUseCaseDep",
    "ListInventoryItemsUseCaseDep",
    "ListKitchenTicketsUseCaseDep",
    "ListOrdersUseCaseDep",
    "ListPaymentsUseCaseDep",
    "ListPurchaseOrdersUseCaseDep",
    "ListStockMovementsUseCaseDep",
    "ListSuppliersUseCaseDep",
    "ListTaxesUseCaseDep",
    "OpenCashDrawerUseCaseDep",
    "RecordPaymentUseCaseDep",
    "RecordStockMovementUseCaseDep",
    "RequestRefundUseCaseDep",
    "RequireBillingManageAtAnyScopeDep",
    "RequireBillingManageDep",
    "RequireBillingManageTenantWideDep",
    "RequireBillingReadAtAnyScopeDep",
    "RequireBillingRefundAtAnyScopeDep",
    "RequireInventoryManageAtAnyScopeDep",
    "RequireInventoryManageDep",
    "RequireInventoryManageTenantWideDep",
    "RequireInventoryReadAtAnyScopeDep",
    "RequireInventoryReadDep",
    "RequireInventoryReadTenantWideDep",
    "RequireKitchenManageAtAnyScopeDep",
    "RequireKitchenReadDep",
    "RequireOrderManageAtAnyScopeDep",
    "RequireOrderManageDep",
    "RequireOrderReadDep",
    "RequirePurchasingManageAtAnyScopeDep",
    "RequirePurchasingManageDep",
    "RequirePurchasingManageTenantWideDep",
    "RequirePurchasingReadDep",
    "RequirePurchasingReadTenantWideDep",
    "RequireReportsReadDep",
    "ReviseRecipeUseCaseDep",
    "SendPurchaseOrderUseCaseDep",
    "UpdateInventoryItemUseCaseDep",
    "UpdateKitchenItemStatusUseCaseDep",
    "UpdateKitchenTicketStatusUseCaseDep",
    "UpdateSupplierUseCaseDep",
    "VoidOrderItemUseCaseDep",
    "VoidOrderUseCaseDep",
]


def get_idempotency_guard(session_factory: SessionFactoryDep) -> IdempotencyGuard:
    return IdempotencyGuard(session_factory)


IdempotencyGuardDep = Annotated[IdempotencyGuard, Depends(get_idempotency_guard)]

RequireOrderManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("order.manage"))
]
RequireOrderReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("order.read"))
]
RequireOrderManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("order.manage"))
]
RequireKitchenReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("kitchen.read"))
]
RequireKitchenManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("kitchen.manage"))
]

# --- Reports (full-day operational simulation gap fix) ---------------------
# branch_id is already in the URL for the one report route this codebase has,
# so the coarse require_branch_permission gate is the only check needed --
# the same shape ListOrdersUseCase/GetOrderUseCase's own router gate uses.
RequireReportsReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("reports.read"))
]

# --- Billing + Payments + Ledger (Sprint 7 Step 4) ------------------------
RequireBillingManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("billing.manage"))
]
RequireBillingManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("billing.manage"))
]
RequireBillingReadAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("billing.read"))
]
# Preserved for the RequestRefundUseCase abstraction (see
# payment_router.py's own docstring) -- not wired to any active route.
RequireBillingRefundAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("billing.refund"))
]
# Taxes/Discounts are tenant-wide reference data (no branch dimension),
# mirroring ModifierGroupRouter's own tenant-wide gate shape.
RequireBillingManageTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("billing.manage"))
]

# --- Inventory + Recipe (Sprint 7 Step 5) ---------------------------------
RequireInventoryManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("inventory.manage"))
]
RequireInventoryReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("inventory.read"))
]
RequireInventoryManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("inventory.manage"))
]
RequireInventoryReadAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("inventory.read"))
]
# InventoryCategory is tenant-level grouping (no branch dimension),
# mirroring Tax/Discount's own tenant-wide gate shape.
RequireInventoryManageTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("inventory.manage"))
]
RequireInventoryReadTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("inventory.read"))
]

# --- Purchasing (Sprint 7 Step 6) ------------------------------------------
RequirePurchasingManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("purchasing.manage"))
]
RequirePurchasingReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("purchasing.read"))
]
RequirePurchasingManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("purchasing.manage"))
]
# Suppliers are tenant-level (Architecture doc SS10: "mirroring how
# Restaurant's own permissions are tenant-wide").
RequirePurchasingManageTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("purchasing.manage"))
]
RequirePurchasingReadTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("purchasing.read"))
]


def get_create_order_use_case(session_factory: SessionFactoryDep) -> CreateOrderUseCase:
    return CreateOrderUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        tab_repository_factory=SQLAlchemyTabRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateOrderUseCaseDep = Annotated[CreateOrderUseCase, Depends(get_create_order_use_case)]


def get_get_order_use_case(session_factory: SessionFactoryDep) -> GetOrderUseCase:
    return GetOrderUseCase(
        session_factory=session_factory, order_repository_factory=SQLAlchemyOrderRepository
    )


GetOrderUseCaseDep = Annotated[GetOrderUseCase, Depends(get_get_order_use_case)]


def get_get_end_of_day_report_use_case(
    session_factory: SessionFactoryDep,
) -> GetEndOfDayReportUseCase:
    return GetEndOfDayReportUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        payment_repository_factory=SQLAlchemyPaymentRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
    )


GetEndOfDayReportUseCaseDep = Annotated[
    GetEndOfDayReportUseCase, Depends(get_get_end_of_day_report_use_case)
]


def get_list_orders_use_case(session_factory: SessionFactoryDep) -> ListOrdersUseCase:
    return ListOrdersUseCase(
        session_factory=session_factory, order_repository_factory=SQLAlchemyOrderRepository
    )


ListOrdersUseCaseDep = Annotated[ListOrdersUseCase, Depends(get_list_orders_use_case)]


def get_add_order_item_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> AddOrderItemUseCase:
    return AddOrderItemUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


AddOrderItemUseCaseDep = Annotated[AddOrderItemUseCase, Depends(get_add_order_item_use_case)]


def get_fire_order_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> FireOrderUseCase:
    return FireOrderUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        kitchen_ticket_repository_factory=SQLAlchemyKitchenTicketRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


FireOrderUseCaseDep = Annotated[FireOrderUseCase, Depends(get_fire_order_use_case)]


# --- Guest QR ordering (Sprint 7 guest-ordering gap fix) --------------------
# No user_id, no ResolveUserPermissionsUseCaseDep -- authorization is
# ensure_guest_order_access re-checking the caller's freshly re-resolved QR
# token against the loaded order's own branch_id/table_id (see that helper's
# own docstring).


def get_guest_add_order_item_use_case(
    session_factory: SessionFactoryDep,
) -> GuestAddOrderItemUseCase:
    return GuestAddOrderItemUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
    )


GuestAddOrderItemUseCaseDep = Annotated[
    GuestAddOrderItemUseCase, Depends(get_guest_add_order_item_use_case)
]


def get_guest_submit_order_use_case(
    session_factory: SessionFactoryDep,
) -> GuestSubmitOrderUseCase:
    return GuestSubmitOrderUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        kitchen_ticket_repository_factory=SQLAlchemyKitchenTicketRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


GuestSubmitOrderUseCaseDep = Annotated[
    GuestSubmitOrderUseCase, Depends(get_guest_submit_order_use_case)
]


def get_guest_get_order_use_case(session_factory: SessionFactoryDep) -> GuestGetOrderUseCase:
    return GuestGetOrderUseCase(
        session_factory=session_factory, order_repository_factory=SQLAlchemyOrderRepository
    )


GuestGetOrderUseCaseDep = Annotated[GuestGetOrderUseCase, Depends(get_guest_get_order_use_case)]


def get_close_order_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CloseOrderUseCase:
    return CloseOrderUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CloseOrderUseCaseDep = Annotated[CloseOrderUseCase, Depends(get_close_order_use_case)]


def get_void_order_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> VoidOrderUseCase:
    return VoidOrderUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


VoidOrderUseCaseDep = Annotated[VoidOrderUseCase, Depends(get_void_order_use_case)]


def get_void_order_item_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> VoidOrderItemUseCase:
    return VoidOrderItemUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


VoidOrderItemUseCaseDep = Annotated[VoidOrderItemUseCase, Depends(get_void_order_item_use_case)]


def get_create_tab_use_case(session_factory: SessionFactoryDep) -> CreateTabUseCase:
    return CreateTabUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        tab_repository_factory=SQLAlchemyTabRepository,
    )


CreateTabUseCaseDep = Annotated[CreateTabUseCase, Depends(get_create_tab_use_case)]


def get_close_tab_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CloseTabUseCase:
    return CloseTabUseCase(
        session_factory=session_factory,
        tab_repository_factory=SQLAlchemyTabRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


CloseTabUseCaseDep = Annotated[CloseTabUseCase, Depends(get_close_tab_use_case)]


def get_list_kitchen_tickets_use_case(
    session_factory: SessionFactoryDep,
) -> ListKitchenTicketsUseCase:
    return ListKitchenTicketsUseCase(
        session_factory=session_factory,
        kitchen_ticket_repository_factory=SQLAlchemyKitchenTicketRepository,
    )


ListKitchenTicketsUseCaseDep = Annotated[
    ListKitchenTicketsUseCase, Depends(get_list_kitchen_tickets_use_case)
]


def get_update_kitchen_ticket_status_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> UpdateKitchenTicketStatusUseCase:
    return UpdateKitchenTicketStatusUseCase(
        session_factory=session_factory,
        kitchen_ticket_repository_factory=SQLAlchemyKitchenTicketRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        recipe_repository_factory=SQLAlchemyRecipeRepository,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        stock_movement_repository_factory=SQLAlchemyStockMovementRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


UpdateKitchenTicketStatusUseCaseDep = Annotated[
    UpdateKitchenTicketStatusUseCase, Depends(get_update_kitchen_ticket_status_use_case)
]


def get_update_kitchen_item_status_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> UpdateKitchenItemStatusUseCase:
    return UpdateKitchenItemStatusUseCase(
        session_factory=session_factory,
        kitchen_ticket_repository_factory=SQLAlchemyKitchenTicketRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


UpdateKitchenItemStatusUseCaseDep = Annotated[
    UpdateKitchenItemStatusUseCase, Depends(get_update_kitchen_item_status_use_case)
]


# --- Billing + Payments + Ledger (Sprint 7 Step 4) ------------------------


def get_create_tax_use_case(session_factory: SessionFactoryDep) -> CreateTaxUseCase:
    return CreateTaxUseCase(
        session_factory=session_factory, tax_repository_factory=SQLAlchemyTaxRepository
    )


CreateTaxUseCaseDep = Annotated[CreateTaxUseCase, Depends(get_create_tax_use_case)]


def get_list_taxes_use_case(session_factory: SessionFactoryDep) -> ListTaxesUseCase:
    return ListTaxesUseCase(
        session_factory=session_factory, tax_repository_factory=SQLAlchemyTaxRepository
    )


ListTaxesUseCaseDep = Annotated[ListTaxesUseCase, Depends(get_list_taxes_use_case)]


def get_create_discount_use_case(session_factory: SessionFactoryDep) -> CreateDiscountUseCase:
    return CreateDiscountUseCase(
        session_factory=session_factory, discount_repository_factory=SQLAlchemyDiscountRepository
    )


CreateDiscountUseCaseDep = Annotated[CreateDiscountUseCase, Depends(get_create_discount_use_case)]


def get_list_discounts_use_case(session_factory: SessionFactoryDep) -> ListDiscountsUseCase:
    return ListDiscountsUseCase(
        session_factory=session_factory, discount_repository_factory=SQLAlchemyDiscountRepository
    )


ListDiscountsUseCaseDep = Annotated[ListDiscountsUseCase, Depends(get_list_discounts_use_case)]


def get_generate_bill_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> GenerateBillUseCase:
    return GenerateBillUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        bill_repository_factory=SQLAlchemyBillRepository,
        tax_repository_factory=SQLAlchemyTaxRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


GenerateBillUseCaseDep = Annotated[GenerateBillUseCase, Depends(get_generate_bill_use_case)]


def get_get_bill_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> GetBillUseCase:
    return GetBillUseCase(
        session_factory=session_factory,
        bill_repository_factory=SQLAlchemyBillRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        payment_repository_factory=SQLAlchemyPaymentRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


GetBillUseCaseDep = Annotated[GetBillUseCase, Depends(get_get_bill_use_case)]


def get_apply_bill_adjustment_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> ApplyBillAdjustmentUseCase:
    return ApplyBillAdjustmentUseCase(
        session_factory=session_factory,
        bill_repository_factory=SQLAlchemyBillRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        discount_repository_factory=SQLAlchemyDiscountRepository,
        payment_repository_factory=SQLAlchemyPaymentRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


ApplyBillAdjustmentUseCaseDep = Annotated[
    ApplyBillAdjustmentUseCase, Depends(get_apply_bill_adjustment_use_case)
]


def get_record_payment_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> RecordPaymentUseCase:
    return RecordPaymentUseCase(
        session_factory=session_factory,
        bill_repository_factory=SQLAlchemyBillRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        payment_repository_factory=SQLAlchemyPaymentRepository,
        ledger_repository_factory=SQLAlchemyLedgerRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


RecordPaymentUseCaseDep = Annotated[RecordPaymentUseCase, Depends(get_record_payment_use_case)]


def get_list_payments_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListPaymentsUseCase:
    return ListPaymentsUseCase(
        session_factory=session_factory,
        bill_repository_factory=SQLAlchemyBillRepository,
        payment_repository_factory=SQLAlchemyPaymentRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


ListPaymentsUseCaseDep = Annotated[ListPaymentsUseCase, Depends(get_list_payments_use_case)]


# Preserved application-layer abstraction, not wired to any active route
# (see payment_router.py's own docstring: RestaurantOS v1 does not
# provide a customer refund workflow).
def get_request_refund_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> RequestRefundUseCase:
    return RequestRefundUseCase(
        session_factory=session_factory,
        payment_repository_factory=SQLAlchemyPaymentRepository,
        bill_repository_factory=SQLAlchemyBillRepository,
        order_repository_factory=SQLAlchemyOrderRepository,
        ledger_repository_factory=SQLAlchemyLedgerRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


RequestRefundUseCaseDep = Annotated[RequestRefundUseCase, Depends(get_request_refund_use_case)]


def get_open_cash_drawer_use_case(session_factory: SessionFactoryDep) -> OpenCashDrawerUseCase:
    return OpenCashDrawerUseCase(
        session_factory=session_factory,
        cash_drawer_repository_factory=SQLAlchemyCashDrawerRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
    )


OpenCashDrawerUseCaseDep = Annotated[OpenCashDrawerUseCase, Depends(get_open_cash_drawer_use_case)]


def get_close_cash_drawer_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CloseCashDrawerUseCase:
    return CloseCashDrawerUseCase(
        session_factory=session_factory,
        cash_drawer_repository_factory=SQLAlchemyCashDrawerRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


CloseCashDrawerUseCaseDep = Annotated[
    CloseCashDrawerUseCase, Depends(get_close_cash_drawer_use_case)
]


def get_get_open_cash_drawer_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> GetOpenCashDrawerUseCase:
    return GetOpenCashDrawerUseCase(
        session_factory=session_factory,
        cash_drawer_repository_factory=SQLAlchemyCashDrawerRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


GetOpenCashDrawerUseCaseDep = Annotated[
    GetOpenCashDrawerUseCase, Depends(get_get_open_cash_drawer_use_case)
]


# --- Inventory + Recipe (Sprint 7 Step 5) ---------------------------------


def get_create_inventory_category_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CreateInventoryCategoryUseCase:
    return CreateInventoryCategoryUseCase(
        session_factory=session_factory,
        inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


CreateInventoryCategoryUseCaseDep = Annotated[
    CreateInventoryCategoryUseCase, Depends(get_create_inventory_category_use_case)
]


def get_list_inventory_categories_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListInventoryCategoriesUseCase:
    return ListInventoryCategoriesUseCase(
        session_factory=session_factory,
        inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


ListInventoryCategoriesUseCaseDep = Annotated[
    ListInventoryCategoriesUseCase, Depends(get_list_inventory_categories_use_case)
]


def get_create_inventory_item_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CreateInventoryItemUseCase:
    return CreateInventoryItemUseCase(
        session_factory=session_factory,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


CreateInventoryItemUseCaseDep = Annotated[
    CreateInventoryItemUseCase, Depends(get_create_inventory_item_use_case)
]


def get_get_inventory_item_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> GetInventoryItemUseCase:
    return GetInventoryItemUseCase(
        session_factory=session_factory,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


GetInventoryItemUseCaseDep = Annotated[
    GetInventoryItemUseCase, Depends(get_get_inventory_item_use_case)
]


def get_list_inventory_items_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListInventoryItemsUseCase:
    return ListInventoryItemsUseCase(
        session_factory=session_factory,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


ListInventoryItemsUseCaseDep = Annotated[
    ListInventoryItemsUseCase, Depends(get_list_inventory_items_use_case)
]


def get_update_inventory_item_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> UpdateInventoryItemUseCase:
    return UpdateInventoryItemUseCase(
        session_factory=session_factory,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


UpdateInventoryItemUseCaseDep = Annotated[
    UpdateInventoryItemUseCase, Depends(get_update_inventory_item_use_case)
]


def get_record_stock_movement_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> RecordStockMovementUseCase:
    return RecordStockMovementUseCase(
        session_factory=session_factory,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        stock_movement_repository_factory=SQLAlchemyStockMovementRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


RecordStockMovementUseCaseDep = Annotated[
    RecordStockMovementUseCase, Depends(get_record_stock_movement_use_case)
]


def get_list_stock_movements_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListStockMovementsUseCase:
    return ListStockMovementsUseCase(
        session_factory=session_factory,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        stock_movement_repository_factory=SQLAlchemyStockMovementRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


ListStockMovementsUseCaseDep = Annotated[
    ListStockMovementsUseCase, Depends(get_list_stock_movements_use_case)
]


def get_revise_recipe_use_case(session_factory: SessionFactoryDep) -> ReviseRecipeUseCase:
    return ReviseRecipeUseCase(
        session_factory=session_factory,
        recipe_repository_factory=SQLAlchemyRecipeRepository,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
    )


ReviseRecipeUseCaseDep = Annotated[ReviseRecipeUseCase, Depends(get_revise_recipe_use_case)]


def get_get_menu_item_recipe_use_case(
    session_factory: SessionFactoryDep,
) -> GetMenuItemRecipeUseCase:
    return GetMenuItemRecipeUseCase(
        session_factory=session_factory,
        recipe_repository_factory=SQLAlchemyRecipeRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
    )


GetMenuItemRecipeUseCaseDep = Annotated[
    GetMenuItemRecipeUseCase, Depends(get_get_menu_item_recipe_use_case)
]


# --- Purchasing (Sprint 7 Step 6) ------------------------------------------


def get_create_supplier_use_case(session_factory: SessionFactoryDep) -> CreateSupplierUseCase:
    return CreateSupplierUseCase(
        session_factory=session_factory,
        supplier_repository_factory=SQLAlchemySupplierRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
    )


CreateSupplierUseCaseDep = Annotated[CreateSupplierUseCase, Depends(get_create_supplier_use_case)]


def get_list_suppliers_use_case(session_factory: SessionFactoryDep) -> ListSuppliersUseCase:
    return ListSuppliersUseCase(
        session_factory=session_factory,
        supplier_repository_factory=SQLAlchemySupplierRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
    )


ListSuppliersUseCaseDep = Annotated[ListSuppliersUseCase, Depends(get_list_suppliers_use_case)]


def get_update_supplier_use_case(session_factory: SessionFactoryDep) -> UpdateSupplierUseCase:
    return UpdateSupplierUseCase(
        session_factory=session_factory,
        supplier_repository_factory=SQLAlchemySupplierRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
    )


UpdateSupplierUseCaseDep = Annotated[UpdateSupplierUseCase, Depends(get_update_supplier_use_case)]


def get_create_purchase_order_use_case(
    session_factory: SessionFactoryDep,
) -> CreatePurchaseOrderUseCase:
    return CreatePurchaseOrderUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
        supplier_repository_factory=SQLAlchemySupplierRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
    )


CreatePurchaseOrderUseCaseDep = Annotated[
    CreatePurchaseOrderUseCase, Depends(get_create_purchase_order_use_case)
]


def get_get_purchase_order_use_case(
    session_factory: SessionFactoryDep,
) -> GetPurchaseOrderUseCase:
    return GetPurchaseOrderUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
    )


GetPurchaseOrderUseCaseDep = Annotated[
    GetPurchaseOrderUseCase, Depends(get_get_purchase_order_use_case)
]


def get_list_purchase_orders_use_case(
    session_factory: SessionFactoryDep,
) -> ListPurchaseOrdersUseCase:
    return ListPurchaseOrdersUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
    )


ListPurchaseOrdersUseCaseDep = Annotated[
    ListPurchaseOrdersUseCase, Depends(get_list_purchase_orders_use_case)
]


def get_add_purchase_order_item_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> AddPurchaseOrderItemUseCase:
    return AddPurchaseOrderItemUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


AddPurchaseOrderItemUseCaseDep = Annotated[
    AddPurchaseOrderItemUseCase, Depends(get_add_purchase_order_item_use_case)
]


def get_send_purchase_order_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> SendPurchaseOrderUseCase:
    return SendPurchaseOrderUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


SendPurchaseOrderUseCaseDep = Annotated[
    SendPurchaseOrderUseCase, Depends(get_send_purchase_order_use_case)
]


def get_cancel_purchase_order_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CancelPurchaseOrderUseCase:
    return CancelPurchaseOrderUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
    )


CancelPurchaseOrderUseCaseDep = Annotated[
    CancelPurchaseOrderUseCase, Depends(get_cancel_purchase_order_use_case)
]


def get_confirm_goods_receipt_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> ConfirmGoodsReceiptUseCase:
    return ConfirmGoodsReceiptUseCase(
        session_factory=session_factory,
        purchase_order_repository_factory=SQLAlchemyPurchaseOrderRepository,
        goods_receipt_repository_factory=SQLAlchemyGoodsReceiptRepository,
        inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
        stock_movement_repository_factory=SQLAlchemyStockMovementRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


ConfirmGoodsReceiptUseCaseDep = Annotated[
    ConfirmGoodsReceiptUseCase, Depends(get_confirm_goods_receipt_use_case)
]
