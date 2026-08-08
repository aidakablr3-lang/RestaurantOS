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
    CloseBranchUseCase,
    CreateBranchUseCase,
    CreateRestaurantUseCase,
    DiscontinueRestaurantUseCase,
    GetBranchUseCase,
    GetRestaurantUseCase,
    ListAccessibleBranchesUseCase,
    ListRestaurantsUseCase,
    ReopenBranchUseCase,
    UpdateBranchUseCase,
    UpdateRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyAddressRepository,
    SQLAlchemyBranchRepository,
    SQLAlchemyRestaurantRepository,
)
from restaurant_os_api.platform.idempotency import IdempotencyGuard
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter

__all__ = [
    "AuthenticatedPrincipalDep",
    "CloseBranchUseCaseDep",
    "CreateBranchUseCaseDep",
    "CreateRestaurantUseCaseDep",
    "DiscontinueRestaurantUseCaseDep",
    "GetBranchUseCaseDep",
    "GetRestaurantUseCaseDep",
    "IdempotencyGuardDep",
    "ListAccessibleBranchesUseCaseDep",
    "ListRestaurantsUseCaseDep",
    "ReopenBranchUseCaseDep",
    "RequireBranchManageDep",
    "RequireBranchManageTenantWideDep",
    "RequireBranchReadAtAnyScopeDep",
    "RequireBranchReadDep",
    "RequireRestaurantManageDep",
    "RequireRestaurantReadDep",
    "UpdateBranchUseCaseDep",
    "UpdateRestaurantUseCaseDep",
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
