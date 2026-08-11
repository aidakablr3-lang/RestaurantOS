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
    ApplyBillAdjustmentUseCase,
    CloseCashDrawerUseCase,
    CloseOrderUseCase,
    CloseTabUseCase,
    CreateDiscountUseCase,
    CreateOrderUseCase,
    CreateTabUseCase,
    CreateTaxUseCase,
    FireOrderUseCase,
    GenerateBillUseCase,
    GetBillUseCase,
    GetOrderUseCase,
    ListDiscountsUseCase,
    ListKitchenTicketsUseCase,
    ListOrdersUseCase,
    ListPaymentsUseCase,
    OpenCashDrawerUseCase,
    RecordPaymentUseCase,
    RequestRefundUseCase,
    UpdateKitchenItemStatusUseCase,
    UpdateKitchenTicketStatusUseCase,
    VoidOrderUseCase,
)
from restaurant_os_api.modules.operations.infrastructure.database.repositories import (
    SQLAlchemyBillRepository,
    SQLAlchemyCashDrawerRepository,
    SQLAlchemyDiscountRepository,
    SQLAlchemyKitchenTicketRepository,
    SQLAlchemyLedgerRepository,
    SQLAlchemyOrderRepository,
    SQLAlchemyPaymentRepository,
    SQLAlchemyTabRepository,
    SQLAlchemyTaxRepository,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
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
    "ApplyBillAdjustmentUseCaseDep",
    "CloseCashDrawerUseCaseDep",
    "CloseOrderUseCaseDep",
    "CloseTabUseCaseDep",
    "CreateDiscountUseCaseDep",
    "CreateOrderUseCaseDep",
    "CreateTabUseCaseDep",
    "CreateTaxUseCaseDep",
    "FireOrderUseCaseDep",
    "GenerateBillUseCaseDep",
    "GetBillUseCaseDep",
    "GetOrderUseCaseDep",
    "IdempotencyGuardDep",
    "ListDiscountsUseCaseDep",
    "ListKitchenTicketsUseCaseDep",
    "ListOrdersUseCaseDep",
    "ListPaymentsUseCaseDep",
    "OpenCashDrawerUseCaseDep",
    "RecordPaymentUseCaseDep",
    "RequestRefundUseCaseDep",
    "RequireBillingManageAtAnyScopeDep",
    "RequireBillingManageDep",
    "RequireBillingManageTenantWideDep",
    "RequireBillingReadAtAnyScopeDep",
    "RequireBillingRefundAtAnyScopeDep",
    "RequireKitchenManageAtAnyScopeDep",
    "RequireKitchenReadDep",
    "RequireOrderManageAtAnyScopeDep",
    "RequireOrderManageDep",
    "RequireOrderReadDep",
    "UpdateKitchenItemStatusUseCaseDep",
    "UpdateKitchenTicketStatusUseCaseDep",
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
RequireBillingRefundAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("billing.refund"))
]
# Taxes/Discounts are tenant-wide reference data (no branch dimension),
# mirroring ModifierGroupRouter's own tenant-wide gate shape.
RequireBillingManageTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("billing.manage"))
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
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


FireOrderUseCaseDep = Annotated[FireOrderUseCase, Depends(get_fire_order_use_case)]


def get_close_order_use_case(
    session_factory: SessionFactoryDep,
    resolve_user_permissions: ResolveUserPermissionsUseCaseDep,
) -> CloseOrderUseCase:
    return CloseOrderUseCase(
        session_factory=session_factory,
        order_repository_factory=SQLAlchemyOrderRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
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
        resolve_user_permissions=resolve_user_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


VoidOrderUseCaseDep = Annotated[VoidOrderUseCase, Depends(get_void_order_use_case)]


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
