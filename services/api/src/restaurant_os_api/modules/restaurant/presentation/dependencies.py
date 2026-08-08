"""Dependency providers wiring concrete Infrastructure to the restaurant
module's Application ports.

Mirrors ``modules.identity.presentation.dependencies``'s exact
convention. Authentication, permission-gating, and the session factory
are **not** duplicated here -- they are cross-cutting, already-built
pieces (Technical Architecture v2.0 SS5.2's shared-kernel DI
singletons), imported directly from identity's own dependencies module,
exactly like ``rbac_router.py`` already reuses ``AuthenticatedPrincipalDep``
and ``require_permission`` rather than rebuilding them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from restaurant_os_api.modules.identity.application.dto import AuthenticatedPrincipalDTO
from restaurant_os_api.modules.identity.presentation.dependencies import (
    AuthenticatedPrincipalDep,
    SessionFactoryDep,
    require_permission,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateRestaurantUseCase,
    DiscontinueRestaurantUseCase,
    GetRestaurantUseCase,
    ListRestaurantsUseCase,
    UpdateRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyRestaurantRepository,
)
from restaurant_os_api.platform.idempotency import IdempotencyGuard
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter

__all__ = [
    "AuthenticatedPrincipalDep",
    "CreateRestaurantUseCaseDep",
    "DiscontinueRestaurantUseCaseDep",
    "GetRestaurantUseCaseDep",
    "IdempotencyGuardDep",
    "ListRestaurantsUseCaseDep",
    "RequireRestaurantManageDep",
    "RequireRestaurantReadDep",
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
