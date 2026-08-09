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
    CreateQRCodeUseCase,
    CreateRestaurantUseCase,
    CreateTableUseCase,
    CreateTableZoneUseCase,
    DiscontinueRestaurantUseCase,
    GetBranchUseCase,
    GetRestaurantUseCase,
    GetTableUseCase,
    GetTableZoneUseCase,
    ListAccessibleBranchesUseCase,
    ListQRCodesUseCase,
    ListRestaurantsUseCase,
    ListTablesUseCase,
    ListTableZonesUseCase,
    ReopenBranchUseCase,
    ReplaceOperatingHoursUseCase,
    ResolveQRCodeUseCase,
    UpdateBranchUseCase,
    UpdateRestaurantUseCase,
    UpdateTableUseCase,
    UpdateTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyAddressRepository,
    SQLAlchemyBranchRepository,
    SQLAlchemyOperatingHoursRepository,
    SQLAlchemyQRCodeRepository,
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
    "CreateQRCodeUseCaseDep",
    "CreateRestaurantUseCaseDep",
    "CreateTableUseCaseDep",
    "CreateTableZoneUseCaseDep",
    "DiscontinueRestaurantUseCaseDep",
    "GetBranchUseCaseDep",
    "GetRestaurantUseCaseDep",
    "GetTableUseCaseDep",
    "GetTableZoneUseCaseDep",
    "IdempotencyGuardDep",
    "ListAccessibleBranchesUseCaseDep",
    "ListQRCodesUseCaseDep",
    "ListRestaurantsUseCaseDep",
    "ListTableZonesUseCaseDep",
    "ListTablesUseCaseDep",
    "QRResolutionRateLimiterDep",
    "ReopenBranchUseCaseDep",
    "ReplaceOperatingHoursUseCaseDep",
    "RequireBranchManageDep",
    "RequireBranchManageTenantWideDep",
    "RequireBranchReadAtAnyScopeDep",
    "RequireBranchReadDep",
    "RequireRestaurantManageDep",
    "RequireRestaurantReadDep",
    "RequireTableManageAtAnyScopeDep",
    "RequireTableManageDep",
    "RequireTableReadAtAnyScopeDep",
    "RequireTableReadDep",
    "ResolveQRCodeUseCaseDep",
    "UpdateBranchUseCaseDep",
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
