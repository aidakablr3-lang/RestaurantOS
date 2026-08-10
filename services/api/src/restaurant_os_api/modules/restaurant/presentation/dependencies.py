"""Dependency providers wiring concrete Infrastructure to the restaurant
module's Application ports.

Mirrors ``modules.identity.presentation.dependencies``'s exact
convention. Authentication, permission-gating, and the session factory
are **not** duplicated here -- they are cross-cutting, already-built
pieces (Technical Architecture v2.0 SS5.2's shared-kernel DI
singletons), imported directly from identity's own dependencies module,
exactly like ``rbac_router.py`` already reuses ``AuthenticatedPrincipalDep``
and ``require_permission`` rather than rebuilding them.

**Branch authorization shape (Step 4.2):** Branch, unlike Restaurant,
has a real branch dimension -- it *is* the branch. Routes with an
existing ``branch_id`` in the URL path (get/update/close/reopen) use
``require_branch_permission``, which reads that same path parameter,
so either a tenant-wide or a branch-scoped grant at that specific
branch is accepted. Creating a *new* branch has no existing
``branch_id`` to scope a check to, so it uses the plain tenant-wide
``require_permission("branch.manage")`` instead -- mirroring how only
a tenant-wide holder (Restaurant Manager/Tenant Owner) can create
branches in the first place; a Branch Manager scoped to one existing
branch has no scope to create a different one. Listing
(``GET /branches``) uses the coarse ``require_permission_at_any_scope``
gate plus ``ListAccessibleBranchesUseCase``'s own fine-grained
filtering (Step 4.0, Decision 2) -- the exact "coarse router gate,
fine-grained use-case decision" split ``rbac_router.py`` already
established for ``roles.assign``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from restaurant_os_api.modules.identity.application.dto import AuthenticatedPrincipalDTO
from restaurant_os_api.modules.identity.presentation.dependencies import (
    AuthenticatedPrincipalDep,
    ResolveUserPermissionsUseCaseDep,
    SessionFactoryDep,
    require_branch_permission,
    require_permission,
    require_permission_at_any_scope,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    ChangeTableStatusUseCase,
    CloseBranchUseCase,
    CreateBranchUseCase,
    CreateMenuCategoryUseCase,
    CreateMenuItemAvailabilityUseCase,
    CreateMenuItemBranchPriceUseCase,
    CreateMenuItemUseCase,
    CreateModifierGroupUseCase,
    CreateModifierUseCase,
    CreateQRCodeUseCase,
    CreateReservationUseCase,
    CreateRestaurantUseCase,
    CreateTableUseCase,
    CreateTableZoneUseCase,
    DiscontinueRestaurantUseCase,
    GetBranchUseCase,
    GetMenuCategoryUseCase,
    GetMenuItemUseCase,
    GetModifierGroupUseCase,
    GetModifierUseCase,
    GetReservationUseCase,
    GetRestaurantUseCase,
    GetTableUseCase,
    GetTableZoneUseCase,
    ListAccessibleBranchesUseCase,
    ListMenuCategoriesUseCase,
    ListMenuItemAvailabilitiesUseCase,
    ListMenuItemBranchPricesUseCase,
    ListMenuItemsUseCase,
    ListModifierGroupsUseCase,
    ListModifiersUseCase,
    ListQRCodesUseCase,
    ListReservationsUseCase,
    ListRestaurantsUseCase,
    ListTablesUseCase,
    ListTableZonesUseCase,
    ReopenBranchUseCase,
    ReplaceMenuItemModifierGroupsUseCase,
    ReplaceOperatingHoursUseCase,
    ResolveQRCodeUseCase,
    UpdateBranchUseCase,
    UpdateMenuCategoryUseCase,
    UpdateMenuItemUseCase,
    UpdateModifierGroupUseCase,
    UpdateModifierUseCase,
    UpdateReservationUseCase,
    UpdateRestaurantUseCase,
    UpdateTableUseCase,
    UpdateTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyAddressRepository,
    SQLAlchemyBranchRepository,
    SQLAlchemyMenuCategoryRepository,
    SQLAlchemyMenuItemAvailabilityRepository,
    SQLAlchemyMenuItemBranchPriceRepository,
    SQLAlchemyMenuItemModifierGroupRepository,
    SQLAlchemyMenuItemRepository,
    SQLAlchemyModifierGroupRepository,
    SQLAlchemyModifierRepository,
    SQLAlchemyOperatingHoursRepository,
    SQLAlchemyQRCodeRepository,
    SQLAlchemyReservationRepository,
    SQLAlchemyRestaurantRepository,
    SQLAlchemyTableRepository,
    SQLAlchemyTableZoneRepository,
)
from restaurant_os_api.platform.idempotency import IdempotencyGuard
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter
from restaurant_os_api.platform.rate_limiting import QRResolutionRateLimiter

__all__ = [
    "AuthenticatedPrincipalDep",
    "ChangeTableStatusUseCaseDep",
    "CloseBranchUseCaseDep",
    "CreateBranchUseCaseDep",
    "CreateMenuCategoryUseCaseDep",
    "CreateMenuItemAvailabilityUseCaseDep",
    "CreateMenuItemBranchPriceUseCaseDep",
    "CreateMenuItemUseCaseDep",
    "CreateModifierGroupUseCaseDep",
    "CreateModifierUseCaseDep",
    "CreateQRCodeUseCaseDep",
    "CreateReservationUseCaseDep",
    "CreateRestaurantUseCaseDep",
    "CreateTableUseCaseDep",
    "CreateTableZoneUseCaseDep",
    "DiscontinueRestaurantUseCaseDep",
    "GetBranchUseCaseDep",
    "GetMenuCategoryUseCaseDep",
    "GetMenuItemUseCaseDep",
    "GetModifierGroupUseCaseDep",
    "GetModifierUseCaseDep",
    "GetReservationUseCaseDep",
    "GetRestaurantUseCaseDep",
    "GetTableUseCaseDep",
    "GetTableZoneUseCaseDep",
    "IdempotencyGuardDep",
    "ListAccessibleBranchesUseCaseDep",
    "ListMenuCategoriesUseCaseDep",
    "ListMenuItemAvailabilitiesUseCaseDep",
    "ListMenuItemBranchPricesUseCaseDep",
    "ListMenuItemsUseCaseDep",
    "ListModifierGroupsUseCaseDep",
    "ListModifiersUseCaseDep",
    "ListQRCodesUseCaseDep",
    "ListReservationsUseCaseDep",
    "ListRestaurantsUseCaseDep",
    "ListTableZonesUseCaseDep",
    "ListTablesUseCaseDep",
    "QRResolutionRateLimiterDep",
    "ReopenBranchUseCaseDep",
    "ReplaceMenuItemModifierGroupsUseCaseDep",
    "ReplaceOperatingHoursUseCaseDep",
    "RequireBranchManageDep",
    "RequireBranchManageTenantWideDep",
    "RequireBranchReadAtAnyScopeDep",
    "RequireBranchReadDep",
    "RequireMenuManageAtAnyScopeDep",
    "RequireMenuManageDep",
    "RequireMenuReadAtAnyScopeDep",
    "RequireMenuReadDep",
    "RequireReservationManageDep",
    "RequireReservationReadDep",
    "RequireRestaurantManageDep",
    "RequireRestaurantReadDep",
    "RequireTableManageAtAnyScopeDep",
    "RequireTableManageDep",
    "RequireTableReadAtAnyScopeDep",
    "RequireTableReadDep",
    "ResolveQRCodeUseCaseDep",
    "UpdateBranchUseCaseDep",
    "UpdateMenuCategoryUseCaseDep",
    "UpdateMenuItemUseCaseDep",
    "UpdateModifierGroupUseCaseDep",
    "UpdateModifierUseCaseDep",
    "UpdateReservationUseCaseDep",
    "UpdateRestaurantUseCaseDep",
    "UpdateTableUseCaseDep",
    "UpdateTableZoneUseCaseDep",
]


def get_idempotency_guard(session_factory: SessionFactoryDep) -> IdempotencyGuard:
    return IdempotencyGuard(session_factory)


IdempotencyGuardDep = Annotated[IdempotencyGuard, Depends(get_idempotency_guard)]


def get_create_restaurant_use_case(session_factory: SessionFactoryDep) -> CreateRestaurantUseCase:
    return CreateRestaurantUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateRestaurantUseCaseDep = Annotated[
    CreateRestaurantUseCase, Depends(get_create_restaurant_use_case)
]


def get_get_restaurant_use_case(session_factory: SessionFactoryDep) -> GetRestaurantUseCase:
    return GetRestaurantUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
    )


GetRestaurantUseCaseDep = Annotated[GetRestaurantUseCase, Depends(get_get_restaurant_use_case)]


def get_list_restaurants_use_case(session_factory: SessionFactoryDep) -> ListRestaurantsUseCase:
    return ListRestaurantsUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
    )


ListRestaurantsUseCaseDep = Annotated[
    ListRestaurantsUseCase, Depends(get_list_restaurants_use_case)
]


def get_update_restaurant_use_case(session_factory: SessionFactoryDep) -> UpdateRestaurantUseCase:
    return UpdateRestaurantUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


UpdateRestaurantUseCaseDep = Annotated[
    UpdateRestaurantUseCase, Depends(get_update_restaurant_use_case)
]


def get_discontinue_restaurant_use_case(
    session_factory: SessionFactoryDep,
) -> DiscontinueRestaurantUseCase:
    return DiscontinueRestaurantUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


DiscontinueRestaurantUseCaseDep = Annotated[
    DiscontinueRestaurantUseCase, Depends(get_discontinue_restaurant_use_case)
]


# Restaurant has no branch dimension (Architecture SS3.1 -- it sits
# above Branch), so every gate here is the plain tenant-wide
# `require_permission`, never `require_branch_permission` or the
# at-any-scope variant -- those exist for entities that actually have
# a branch_id, which Restaurant does not.
RequireRestaurantManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("restaurant.manage"))
]
RequireRestaurantReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("restaurant.read"))
]


# --- Branch (Step 4.2) ---------------------------------------------------


def get_create_branch_use_case(session_factory: SessionFactoryDep) -> CreateBranchUseCase:
    return CreateBranchUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateBranchUseCaseDep = Annotated[CreateBranchUseCase, Depends(get_create_branch_use_case)]


def get_get_branch_use_case(session_factory: SessionFactoryDep) -> GetBranchUseCase:
    return GetBranchUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
        operating_hours_repository_factory=SQLAlchemyOperatingHoursRepository,
    )


GetBranchUseCaseDep = Annotated[GetBranchUseCase, Depends(get_get_branch_use_case)]


def get_update_branch_use_case(session_factory: SessionFactoryDep) -> UpdateBranchUseCase:
    return UpdateBranchUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


UpdateBranchUseCaseDep = Annotated[UpdateBranchUseCase, Depends(get_update_branch_use_case)]


def get_close_branch_use_case(session_factory: SessionFactoryDep) -> CloseBranchUseCase:
    return CloseBranchUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CloseBranchUseCaseDep = Annotated[CloseBranchUseCase, Depends(get_close_branch_use_case)]


def get_reopen_branch_use_case(session_factory: SessionFactoryDep) -> ReopenBranchUseCase:
    return ReopenBranchUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        address_repository_factory=SQLAlchemyAddressRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


ReopenBranchUseCaseDep = Annotated[ReopenBranchUseCase, Depends(get_reopen_branch_use_case)]


def get_list_accessible_branches_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListAccessibleBranchesUseCase:
    return ListAccessibleBranchesUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_permissions,
    )


ListAccessibleBranchesUseCaseDep = Annotated[
    ListAccessibleBranchesUseCase, Depends(get_list_accessible_branches_use_case)
]

RequireBranchManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("branch.manage"))
]
RequireBranchReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("branch.read"))
]
RequireBranchManageTenantWideDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("branch.manage"))
]
RequireBranchReadAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("branch.read"))
]


# --- Operating Hours (Step 4.3) -------------------------------------------
# Gated by branch.manage/branch.read (not table.manage) -- confirmed with
# the user: Architecture SS8's Branch Details screen groups Branch +
# Address + OperatingHours as one branch-configuration unit, matching how
# Address is already gated under branch.manage.


def get_replace_operating_hours_use_case(
    session_factory: SessionFactoryDep,
) -> ReplaceOperatingHoursUseCase:
    return ReplaceOperatingHoursUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        operating_hours_repository_factory=SQLAlchemyOperatingHoursRepository,
    )


ReplaceOperatingHoursUseCaseDep = Annotated[
    ReplaceOperatingHoursUseCase, Depends(get_replace_operating_hours_use_case)
]


# --- TableZone (Step 4.4) --------------------------------------------------
# Gated by table.manage/table.read -- the seeded permission descriptions
# name "dining areas, tables, and QR codes" explicitly (migration 0003),
# unlike Operating Hours' genuine branch.manage-vs-table.manage ambiguity,
# so no confirmation was needed here.


def get_create_table_zone_use_case(session_factory: SessionFactoryDep) -> CreateTableZoneUseCase:
    return CreateTableZoneUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_zone_repository_factory=SQLAlchemyTableZoneRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateTableZoneUseCaseDep = Annotated[
    CreateTableZoneUseCase, Depends(get_create_table_zone_use_case)
]


def get_get_table_zone_use_case(session_factory: SessionFactoryDep) -> GetTableZoneUseCase:
    return GetTableZoneUseCase(
        session_factory=session_factory,
        table_zone_repository_factory=SQLAlchemyTableZoneRepository,
    )


GetTableZoneUseCaseDep = Annotated[GetTableZoneUseCase, Depends(get_get_table_zone_use_case)]


def get_list_table_zones_use_case(session_factory: SessionFactoryDep) -> ListTableZonesUseCase:
    return ListTableZonesUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_zone_repository_factory=SQLAlchemyTableZoneRepository,
    )


ListTableZonesUseCaseDep = Annotated[ListTableZonesUseCase, Depends(get_list_table_zones_use_case)]


def get_update_table_zone_use_case(session_factory: SessionFactoryDep) -> UpdateTableZoneUseCase:
    return UpdateTableZoneUseCase(
        session_factory=session_factory,
        table_zone_repository_factory=SQLAlchemyTableZoneRepository,
    )


UpdateTableZoneUseCaseDep = Annotated[
    UpdateTableZoneUseCase, Depends(get_update_table_zone_use_case)
]

RequireTableManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("table.manage"))
]
RequireTableReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("table.read"))
]


# --- Table (Step 4.5) -------------------------------------------------------
# CRUD routes are nested under branch_id (same table.manage/table.read gate
# as TableZone). The one exception is the status-change route, which
# Architecture SS7 puts at a *flat* /api/v1/tables/{id}/status path -- no
# branch_id in the URL for require_branch_permission to read. That route
# uses the coarse require_permission_at_any_scope("table.manage") gate here
# plus ChangeTableStatusUseCase's own fine-grained resolve_and_authorize_branch
# call, mirroring ListAccessibleBranchesUseCase's established split.


def get_create_table_use_case(session_factory: SessionFactoryDep) -> CreateTableUseCase:
    return CreateTableUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_zone_repository_factory=SQLAlchemyTableZoneRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateTableUseCaseDep = Annotated[CreateTableUseCase, Depends(get_create_table_use_case)]


def get_get_table_use_case(session_factory: SessionFactoryDep) -> GetTableUseCase:
    return GetTableUseCase(
        session_factory=session_factory,
        table_repository_factory=SQLAlchemyTableRepository,
    )


GetTableUseCaseDep = Annotated[GetTableUseCase, Depends(get_get_table_use_case)]


def get_list_tables_use_case(session_factory: SessionFactoryDep) -> ListTablesUseCase:
    return ListTablesUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_repository_factory=SQLAlchemyTableRepository,
    )


ListTablesUseCaseDep = Annotated[ListTablesUseCase, Depends(get_list_tables_use_case)]


def get_update_table_use_case(session_factory: SessionFactoryDep) -> UpdateTableUseCase:
    return UpdateTableUseCase(
        session_factory=session_factory,
        table_repository_factory=SQLAlchemyTableRepository,
        table_zone_repository_factory=SQLAlchemyTableZoneRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


UpdateTableUseCaseDep = Annotated[UpdateTableUseCase, Depends(get_update_table_use_case)]


def get_change_table_status_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ChangeTableStatusUseCase:
    return ChangeTableStatusUseCase(
        session_factory=session_factory,
        table_repository_factory=SQLAlchemyTableRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        resolve_user_permissions=resolve_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


ChangeTableStatusUseCaseDep = Annotated[
    ChangeTableStatusUseCase, Depends(get_change_table_status_use_case)
]

RequireTableManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("table.manage"))
]


# --- QR Code management (Step 4.6) ------------------------------------------
# Architecture SS7 puts both management routes at a *flat*
# /api/v1/tables/{id}/qr-codes path -- no branch_id in the URL, so both use
# the same coarse-gate/fine-grained-use-case split as ChangeTableStatusUseCase
# (Step 4.5). The unauthenticated resolution endpoint (GET /api/v1/qr/{token})
# is explicitly out of scope for this step -- see ADR 0001 and the user's own
# Step 4.6/4.7 split.


def get_create_qr_code_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> CreateQRCodeUseCase:
    return CreateQRCodeUseCase(
        session_factory=session_factory,
        table_repository_factory=SQLAlchemyTableRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        qr_code_repository_factory=SQLAlchemyQRCodeRepository,
        resolve_user_permissions=resolve_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateQRCodeUseCaseDep = Annotated[CreateQRCodeUseCase, Depends(get_create_qr_code_use_case)]


def get_list_qr_codes_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListQRCodesUseCase:
    return ListQRCodesUseCase(
        session_factory=session_factory,
        table_repository_factory=SQLAlchemyTableRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        qr_code_repository_factory=SQLAlchemyQRCodeRepository,
        resolve_user_permissions=resolve_permissions,
    )


ListQRCodesUseCaseDep = Annotated[ListQRCodesUseCase, Depends(get_list_qr_codes_use_case)]

RequireTableReadAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("table.read"))
]


# --- QR Code resolution (Step 4.7) ------------------------------------------
# Deliberately no RequireXxxDep of any kind is used anywhere in this section
# -- GET /api/v1/qr/{token} (ADR 0001) is unauthenticated by design, and
# nothing here consults AuthenticatedPrincipalDep, RBAC, or tenant context.
# The only guard is QRResolutionRateLimiter, itself unauthenticated.


def get_qr_resolution_rate_limiter(session_factory: SessionFactoryDep) -> QRResolutionRateLimiter:
    return QRResolutionRateLimiter(session_factory)


QRResolutionRateLimiterDep = Annotated[
    QRResolutionRateLimiter, Depends(get_qr_resolution_rate_limiter)
]


def get_resolve_qr_code_use_case(
    session_factory: SessionFactoryDep,
    rate_limiter: QRResolutionRateLimiterDep,
) -> ResolveQRCodeUseCase:
    return ResolveQRCodeUseCase(
        session_factory=session_factory,
        qr_code_repository_factory=SQLAlchemyQRCodeRepository,
        rate_limiter=rate_limiter,
    )


ResolveQRCodeUseCaseDep = Annotated[ResolveQRCodeUseCase, Depends(get_resolve_qr_code_use_case)]


# --- Menu Catalogue: MenuCategory + MenuItem (Step 4.8) ---------------------
# Neither entity has a branch dimension (Architecture SS3.1 -- both belong to
# Restaurant, deliberately not Branch, per SS3's "no Menu wrapper" decision),
# so every gate here is the plain tenant-wide require_permission("menu.read"/
# "menu.manage"), the same shape RequireRestaurantManageDep/
# RequireRestaurantReadDep already use for the same reason. ModifierGroup/
# Modifier/MenuItemModifierGroup are wired below (Step 4.9). MenuItemBranchPrice,
# MenuItemAvailability, and Reservation remain out of scope.


def get_create_menu_category_use_case(
    session_factory: SessionFactoryDep,
) -> CreateMenuCategoryUseCase:
    return CreateMenuCategoryUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateMenuCategoryUseCaseDep = Annotated[
    CreateMenuCategoryUseCase, Depends(get_create_menu_category_use_case)
]


def get_get_menu_category_use_case(session_factory: SessionFactoryDep) -> GetMenuCategoryUseCase:
    return GetMenuCategoryUseCase(
        session_factory=session_factory,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
    )


GetMenuCategoryUseCaseDep = Annotated[
    GetMenuCategoryUseCase, Depends(get_get_menu_category_use_case)
]


def get_list_menu_categories_use_case(
    session_factory: SessionFactoryDep,
) -> ListMenuCategoriesUseCase:
    return ListMenuCategoriesUseCase(
        session_factory=session_factory,
        restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
    )


ListMenuCategoriesUseCaseDep = Annotated[
    ListMenuCategoriesUseCase, Depends(get_list_menu_categories_use_case)
]


def get_update_menu_category_use_case(
    session_factory: SessionFactoryDep,
) -> UpdateMenuCategoryUseCase:
    return UpdateMenuCategoryUseCase(
        session_factory=session_factory,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
    )


UpdateMenuCategoryUseCaseDep = Annotated[
    UpdateMenuCategoryUseCase, Depends(get_update_menu_category_use_case)
]


def get_create_menu_item_use_case(session_factory: SessionFactoryDep) -> CreateMenuItemUseCase:
    return CreateMenuItemUseCase(
        session_factory=session_factory,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateMenuItemUseCaseDep = Annotated[CreateMenuItemUseCase, Depends(get_create_menu_item_use_case)]


def get_get_menu_item_use_case(session_factory: SessionFactoryDep) -> GetMenuItemUseCase:
    return GetMenuItemUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
    )


GetMenuItemUseCaseDep = Annotated[GetMenuItemUseCase, Depends(get_get_menu_item_use_case)]


def get_list_menu_items_use_case(session_factory: SessionFactoryDep) -> ListMenuItemsUseCase:
    return ListMenuItemsUseCase(
        session_factory=session_factory,
        menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
    )


ListMenuItemsUseCaseDep = Annotated[ListMenuItemsUseCase, Depends(get_list_menu_items_use_case)]


def get_update_menu_item_use_case(session_factory: SessionFactoryDep) -> UpdateMenuItemUseCase:
    return UpdateMenuItemUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


UpdateMenuItemUseCaseDep = Annotated[UpdateMenuItemUseCase, Depends(get_update_menu_item_use_case)]

RequireMenuManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("menu.manage"))
]
RequireMenuReadDep = Annotated[AuthenticatedPrincipalDTO, Depends(require_permission("menu.read"))]


# --- Modifiers: ModifierGroup + Modifier + attachment (Step 4.9) ------------
# ModifierGroup/Modifier have no branch dimension either (Architecture SS3.1
# -- both belong directly to the tenant, Data Architecture v2.0 Group F), so
# every gate here reuses the same menu.read/menu.manage pair Step 4.8 already
# wired -- the permission's own seeded description ("modifiers, pricing, and
# availability") already covers this. MenuItemBranchPrice, MenuItemAvailability,
# and Reservation remain out of scope.


def get_create_modifier_group_use_case(
    session_factory: SessionFactoryDep,
) -> CreateModifierGroupUseCase:
    return CreateModifierGroupUseCase(
        session_factory=session_factory,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateModifierGroupUseCaseDep = Annotated[
    CreateModifierGroupUseCase, Depends(get_create_modifier_group_use_case)
]


def get_get_modifier_group_use_case(
    session_factory: SessionFactoryDep,
) -> GetModifierGroupUseCase:
    return GetModifierGroupUseCase(
        session_factory=session_factory,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
    )


GetModifierGroupUseCaseDep = Annotated[
    GetModifierGroupUseCase, Depends(get_get_modifier_group_use_case)
]


def get_list_modifier_groups_use_case(
    session_factory: SessionFactoryDep,
) -> ListModifierGroupsUseCase:
    return ListModifierGroupsUseCase(
        session_factory=session_factory,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
    )


ListModifierGroupsUseCaseDep = Annotated[
    ListModifierGroupsUseCase, Depends(get_list_modifier_groups_use_case)
]


def get_update_modifier_group_use_case(
    session_factory: SessionFactoryDep,
) -> UpdateModifierGroupUseCase:
    return UpdateModifierGroupUseCase(
        session_factory=session_factory,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
    )


UpdateModifierGroupUseCaseDep = Annotated[
    UpdateModifierGroupUseCase, Depends(get_update_modifier_group_use_case)
]


def get_create_modifier_use_case(session_factory: SessionFactoryDep) -> CreateModifierUseCase:
    return CreateModifierUseCase(
        session_factory=session_factory,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
        modifier_repository_factory=SQLAlchemyModifierRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateModifierUseCaseDep = Annotated[CreateModifierUseCase, Depends(get_create_modifier_use_case)]


def get_get_modifier_use_case(session_factory: SessionFactoryDep) -> GetModifierUseCase:
    return GetModifierUseCase(
        session_factory=session_factory,
        modifier_repository_factory=SQLAlchemyModifierRepository,
    )


GetModifierUseCaseDep = Annotated[GetModifierUseCase, Depends(get_get_modifier_use_case)]


def get_list_modifiers_use_case(session_factory: SessionFactoryDep) -> ListModifiersUseCase:
    return ListModifiersUseCase(
        session_factory=session_factory,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
        modifier_repository_factory=SQLAlchemyModifierRepository,
    )


ListModifiersUseCaseDep = Annotated[ListModifiersUseCase, Depends(get_list_modifiers_use_case)]


def get_update_modifier_use_case(session_factory: SessionFactoryDep) -> UpdateModifierUseCase:
    return UpdateModifierUseCase(
        session_factory=session_factory,
        modifier_repository_factory=SQLAlchemyModifierRepository,
    )


UpdateModifierUseCaseDep = Annotated[UpdateModifierUseCase, Depends(get_update_modifier_use_case)]


def get_replace_menu_item_modifier_groups_use_case(
    session_factory: SessionFactoryDep,
) -> ReplaceMenuItemModifierGroupsUseCase:
    return ReplaceMenuItemModifierGroupsUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        modifier_group_repository_factory=SQLAlchemyModifierGroupRepository,
        menu_item_modifier_group_repository_factory=SQLAlchemyMenuItemModifierGroupRepository,
    )


ReplaceMenuItemModifierGroupsUseCaseDep = Annotated[
    ReplaceMenuItemModifierGroupsUseCase, Depends(get_replace_menu_item_modifier_groups_use_case)
]


# --- MenuItemBranchPrice + MenuItemAvailability (Step 4.10) -----------------
# Both routes are flat (no branch_id in the URL -- it arrives in the body),
# the same shape ChangeTableStatusUseCase (Step 4.5) already established, so
# both use the coarse require_permission_at_any_scope("menu.manage"/
# "menu.read") gate here plus each use case's own fine-grained
# resolve_and_authorize_branch (create) or tenant-wide-vs-branch-scoped
# filtering (list) call.


def get_create_menu_item_branch_price_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> CreateMenuItemBranchPriceUseCase:
    return CreateMenuItemBranchPriceUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        menu_item_branch_price_repository_factory=SQLAlchemyMenuItemBranchPriceRepository,
        resolve_user_permissions=resolve_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateMenuItemBranchPriceUseCaseDep = Annotated[
    CreateMenuItemBranchPriceUseCase, Depends(get_create_menu_item_branch_price_use_case)
]


def get_list_menu_item_branch_prices_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListMenuItemBranchPricesUseCase:
    return ListMenuItemBranchPricesUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        menu_item_branch_price_repository_factory=SQLAlchemyMenuItemBranchPriceRepository,
        resolve_user_permissions=resolve_permissions,
    )


ListMenuItemBranchPricesUseCaseDep = Annotated[
    ListMenuItemBranchPricesUseCase, Depends(get_list_menu_item_branch_prices_use_case)
]


def get_create_menu_item_availability_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> CreateMenuItemAvailabilityUseCase:
    return CreateMenuItemAvailabilityUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        branch_repository_factory=SQLAlchemyBranchRepository,
        menu_item_availability_repository_factory=SQLAlchemyMenuItemAvailabilityRepository,
        resolve_user_permissions=resolve_permissions,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateMenuItemAvailabilityUseCaseDep = Annotated[
    CreateMenuItemAvailabilityUseCase, Depends(get_create_menu_item_availability_use_case)
]


def get_list_menu_item_availabilities_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ListMenuItemAvailabilitiesUseCase:
    return ListMenuItemAvailabilitiesUseCase(
        session_factory=session_factory,
        menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        menu_item_availability_repository_factory=SQLAlchemyMenuItemAvailabilityRepository,
        resolve_user_permissions=resolve_permissions,
    )


ListMenuItemAvailabilitiesUseCaseDep = Annotated[
    ListMenuItemAvailabilitiesUseCase, Depends(get_list_menu_item_availabilities_use_case)
]

RequireMenuManageAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("menu.manage"))
]
RequireMenuReadAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("menu.read"))
]


# --- Reservation (Step 4.11) -------------------------------------------------
# All three routes (POST/GET-list/PATCH) are nested under branch_id, the same
# shape Table's own CRUD routes use -- no flat status-change route exists for
# Reservation (Architecture SS7 gives it none), so every gate here is the
# plain require_branch_permission("reservation.manage"/"reservation.read"),
# never the coarse at-any-scope + resolve_and_authorize_branch split
# ChangeTableStatusUseCase needs for its one flat route.


def get_create_reservation_use_case(
    session_factory: SessionFactoryDep,
) -> CreateReservationUseCase:
    return CreateReservationUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        reservation_repository_factory=SQLAlchemyReservationRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


CreateReservationUseCaseDep = Annotated[
    CreateReservationUseCase, Depends(get_create_reservation_use_case)
]


def get_get_reservation_use_case(session_factory: SessionFactoryDep) -> GetReservationUseCase:
    return GetReservationUseCase(
        session_factory=session_factory,
        reservation_repository_factory=SQLAlchemyReservationRepository,
    )


GetReservationUseCaseDep = Annotated[GetReservationUseCase, Depends(get_get_reservation_use_case)]


def get_list_reservations_use_case(
    session_factory: SessionFactoryDep,
) -> ListReservationsUseCase:
    return ListReservationsUseCase(
        session_factory=session_factory,
        branch_repository_factory=SQLAlchemyBranchRepository,
        reservation_repository_factory=SQLAlchemyReservationRepository,
    )


ListReservationsUseCaseDep = Annotated[
    ListReservationsUseCase, Depends(get_list_reservations_use_case)
]


def get_update_reservation_use_case(
    session_factory: SessionFactoryDep,
) -> UpdateReservationUseCase:
    return UpdateReservationUseCase(
        session_factory=session_factory,
        reservation_repository_factory=SQLAlchemyReservationRepository,
        table_repository_factory=SQLAlchemyTableRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


UpdateReservationUseCaseDep = Annotated[
    UpdateReservationUseCase, Depends(get_update_reservation_use_case)
]

RequireReservationManageDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("reservation.manage"))
]
RequireReservationReadDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_branch_permission("reservation.read"))
]
