"""Shared fixtures and real-use-case wiring for the onboarding step
integration tests (Phase 1 design doc SSE step 5's 14 concrete steps).

Every ``make_*_step`` function below constructs one concrete
``OnboardingStep`` with *real* use cases wired to real
``SQLAlchemyXxxRepository`` classes -- no fakes, no mocks -- exactly the
pattern ``tests/integration/modules/identity/test_owner_provisioning.py``
already established for ``TenantProvisioningService``. Each test file
imports the ``make_*_step`` function(s) it needs directly.

The ``*_ctx`` fixtures below chain the steps that must run *before* the
step under test, executing each prerequisite for real against Postgres
and threading the resulting ids through a real ``OnboardingRunContext``
-- never a hand-built context with made-up ids. A given test then
constructs (and, where the fixture chain doesn't already cover it,
executes) the one step it's actually testing.

``admin_engine`` mirrors ``test_owner_provisioning.py``'s own fixture of
the same name exactly: a connection as the table *owner*
(``TEST_DATABASE_URL`` itself), which genuinely bypasses Row-Level
Security, unlike ``session_factory``/the ``engine`` fixture from
``tests/integration/conftest.py`` (the deliberately unprivileged,
RLS-*enforcing* role). Used only for the raw-SQL "delete/invalidate the
row out from under the step" half of each test -- everything else goes
through real use cases.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.services.tenant_provisioning_service import (
    TenantProvisioningService,
)
from restaurant_os_api.modules.identity.application.use_cases.assign_user_role import (
    AssignUserRoleUseCase,
)
from restaurant_os_api.modules.identity.application.use_cases.create_user import CreateUserUseCase
from restaurant_os_api.modules.identity.application.use_cases.get_owner_activation_token_status import (
    GetOwnerActivationTokenStatusUseCase,
)
from restaurant_os_api.modules.identity.application.use_cases.get_role_by_name import (
    GetRoleByNameUseCase,
)
from restaurant_os_api.modules.identity.application.use_cases.get_tenant import GetTenantUseCase
from restaurant_os_api.modules.identity.application.use_cases.get_user import GetUserUseCase
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemyOwnerActivationTokenRepository,
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemySubscriptionRepository,
    SQLAlchemyTenantDirectoryRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JWTTokenService,
)
from restaurant_os_api.modules.onboarding.application.steps.add_inventory_step import (
    AddInventoryStep,
    AddInventoryStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.add_recipes_step import AddRecipesStep
from restaurant_os_api.modules.onboarding.application.steps.configure_tax_step import (
    ConfigureTaxStep,
)
from restaurant_os_api.modules.onboarding.application.steps.create_branch_step import (
    CreateBranchStep,
    CreateBranchStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_kitchen_staff_step import (
    CreateKitchenStaffStep,
)
from restaurant_os_api.modules.onboarding.application.steps.create_manager_step import (
    CreateManagerStep,
)
from restaurant_os_api.modules.onboarding.application.steps.create_menu_category_step import (
    CreateMenuCategoryStep,
    CreateMenuCategoryStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_menu_items_step import (
    CreateMenuItemsStep,
    CreateMenuItemsStepInput,
    MenuItemSpec,
)
from restaurant_os_api.modules.onboarding.application.steps.create_restaurant_step import (
    CreateRestaurantStep,
    CreateRestaurantStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_table_step import (
    CreateTableStep,
    CreateTableStepInput,
    TableSpec,
)
from restaurant_os_api.modules.onboarding.application.steps.create_table_zone_step import (
    CreateTableZoneStep,
    CreateTableZoneStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_waiters_step import (
    CreateWaitersStep,
)
from restaurant_os_api.modules.onboarding.application.steps.generate_qr_codes_step import (
    GenerateQrCodesStep,
)
from restaurant_os_api.modules.onboarding.application.steps.provision_tenant_step import (
    ProvisionTenantStep,
    ProvisionTenantStepInput,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import OnboardingRunContext
from restaurant_os_api.modules.operations.application.use_cases.create_inventory_category import (
    CreateInventoryCategoryUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.create_inventory_item import (
    CreateInventoryItemUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.create_tax import CreateTaxUseCase
from restaurant_os_api.modules.operations.application.use_cases.get_inventory_category import (
    GetInventoryCategoryUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.get_inventory_item import (
    GetInventoryItemUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.get_menu_item_recipe import (
    GetMenuItemRecipeUseCase,
)
from restaurant_os_api.modules.operations.application.use_cases.list_taxes import ListTaxesUseCase
from restaurant_os_api.modules.operations.application.use_cases.revise_recipe import (
    ReviseRecipeUseCase,
)
from restaurant_os_api.modules.operations.infrastructure.database.repositories import (
    SQLAlchemyInventoryCategoryRepository,
    SQLAlchemyInventoryItemRepository,
    SQLAlchemyRecipeRepository,
    SQLAlchemyTaxRepository,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_branch import (
    CreateBranchUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_menu_category import (
    CreateMenuCategoryUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_menu_item import (
    CreateMenuItemUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_qr_code import (
    CreateQRCodeUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_restaurant import (
    CreateRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_table import (
    CreateTableUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.create_table_zone import (
    CreateTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_branch import GetBranchUseCase
from restaurant_os_api.modules.restaurant.application.use_cases.get_menu_category import (
    GetMenuCategoryUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_menu_item import (
    GetMenuItemUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_restaurant import (
    GetRestaurantUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.get_table import GetTableUseCase
from restaurant_os_api.modules.restaurant.application.use_cases.get_table_zone import (
    GetTableZoneUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.list_qr_codes import (
    ListQRCodesUseCase,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyAddressRepository,
    SQLAlchemyBranchRepository,
    SQLAlchemyMenuCategoryRepository,
    SQLAlchemyMenuItemRepository,
    SQLAlchemyOperatingHoursRepository,
    SQLAlchemyQRCodeRepository,
    SQLAlchemyRestaurantRepository,
    SQLAlchemyTableRepository,
    SQLAlchemyTableZoneRepository,
)
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter

# --- Cross-cutting singletons, same shape as test_owner_provisioning.py ---


def make_token_service() -> JWTTokenService:
    return JWTTokenService(
        private_key="unused-in-these-tests",
        public_key="unused-in-these-tests",
        issuer="restaurantos-test",
        access_ttl_seconds=900,
    )


def make_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def unique_email(prefix: str) -> str:
    return f"{prefix}-{generate_ulid()}@example.com".lower()


# --- admin_engine: genuinely bypasses RLS, table-owner connection --------


@pytest_asyncio.fixture
async def admin_engine() -> AsyncGenerator[AsyncEngine]:
    """See this module's own docstring -- identical fixture to
    ``test_owner_provisioning.py``'s, duplicated here (not imported)
    since that file is a test module, not a shared fixture library."""
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    yield engine
    await engine.dispose()


# --- Real use-case / step wiring, one make_* per concrete step -----------


def make_resolve_user_permissions_use_case(
    session_factory: async_sessionmaker[AsyncSession],
) -> ResolveUserPermissionsUseCase:
    return ResolveUserPermissionsUseCase(
        session_factory=session_factory,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
    )


def make_provisioning_service(session_factory: async_sessionmaker[AsyncSession]) -> TenantProvisioningService:
    return TenantProvisioningService(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
        feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        owner_activation_token_repository_factory=SQLAlchemyOwnerActivationTokenRepository,
        token_service=make_token_service(),
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def make_provision_tenant_step(session_factory: async_sessionmaker[AsyncSession]) -> ProvisionTenantStep:
    return ProvisionTenantStep(
        provisioning_service=make_provisioning_service(session_factory),
        get_tenant_use_case=GetTenantUseCase(
            session_factory=session_factory, tenant_repository_factory=SQLAlchemyTenantRepository
        ),
        get_user_use_case=GetUserUseCase(
            session_factory=session_factory, user_repository_factory=SQLAlchemyUserRepository
        ),
        resolve_user_permissions_use_case=make_resolve_user_permissions_use_case(session_factory),
        get_owner_activation_token_status_use_case=GetOwnerActivationTokenStatusUseCase(
            session_factory=session_factory,
            owner_activation_token_repository_factory=SQLAlchemyOwnerActivationTokenRepository,
        ),
    )


def make_create_restaurant_step(session_factory: async_sessionmaker[AsyncSession]) -> CreateRestaurantStep:
    return CreateRestaurantStep(
        create_restaurant_use_case=CreateRestaurantUseCase(
            session_factory=session_factory,
            restaurant_repository_factory=SQLAlchemyRestaurantRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_restaurant_use_case=GetRestaurantUseCase(
            session_factory=session_factory,
            restaurant_repository_factory=SQLAlchemyRestaurantRepository,
        ),
    )


def make_create_branch_step(session_factory: async_sessionmaker[AsyncSession]) -> CreateBranchStep:
    return CreateBranchStep(
        create_branch_use_case=CreateBranchUseCase(
            session_factory=session_factory,
            restaurant_repository_factory=SQLAlchemyRestaurantRepository,
            branch_repository_factory=SQLAlchemyBranchRepository,
            address_repository_factory=SQLAlchemyAddressRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_branch_use_case=GetBranchUseCase(
            session_factory=session_factory,
            branch_repository_factory=SQLAlchemyBranchRepository,
            address_repository_factory=SQLAlchemyAddressRepository,
            operating_hours_repository_factory=SQLAlchemyOperatingHoursRepository,
        ),
    )


def make_create_table_zone_step(session_factory: async_sessionmaker[AsyncSession]) -> CreateTableZoneStep:
    return CreateTableZoneStep(
        create_table_zone_use_case=CreateTableZoneUseCase(
            session_factory=session_factory,
            branch_repository_factory=SQLAlchemyBranchRepository,
            table_zone_repository_factory=SQLAlchemyTableZoneRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_table_zone_use_case=GetTableZoneUseCase(
            session_factory=session_factory,
            table_zone_repository_factory=SQLAlchemyTableZoneRepository,
        ),
    )


def make_create_table_step(session_factory: async_sessionmaker[AsyncSession]) -> CreateTableStep:
    return CreateTableStep(
        create_table_use_case=CreateTableUseCase(
            session_factory=session_factory,
            branch_repository_factory=SQLAlchemyBranchRepository,
            table_zone_repository_factory=SQLAlchemyTableZoneRepository,
            table_repository_factory=SQLAlchemyTableRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_table_use_case=GetTableUseCase(
            session_factory=session_factory, table_repository_factory=SQLAlchemyTableRepository
        ),
    )


def make_generate_qr_codes_step(session_factory: async_sessionmaker[AsyncSession]) -> GenerateQrCodesStep:
    resolve_permissions = make_resolve_user_permissions_use_case(session_factory)
    return GenerateQrCodesStep(
        create_qr_code_use_case=CreateQRCodeUseCase(
            session_factory=session_factory,
            table_repository_factory=SQLAlchemyTableRepository,
            branch_repository_factory=SQLAlchemyBranchRepository,
            qr_code_repository_factory=SQLAlchemyQRCodeRepository,
            resolve_user_permissions=resolve_permissions,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        list_qr_codes_use_case=ListQRCodesUseCase(
            session_factory=session_factory,
            table_repository_factory=SQLAlchemyTableRepository,
            branch_repository_factory=SQLAlchemyBranchRepository,
            qr_code_repository_factory=SQLAlchemyQRCodeRepository,
            resolve_user_permissions=resolve_permissions,
        ),
    )


def make_configure_tax_step(session_factory: async_sessionmaker[AsyncSession]) -> ConfigureTaxStep:
    return ConfigureTaxStep(
        create_tax_use_case=CreateTaxUseCase(
            session_factory=session_factory, tax_repository_factory=SQLAlchemyTaxRepository
        ),
        list_taxes_use_case=ListTaxesUseCase(
            session_factory=session_factory, tax_repository_factory=SQLAlchemyTaxRepository
        ),
    )


@dataclass(slots=True)
class _StaffStepUseCases:
    """Shared wiring for the three staff-creation steps -- all three
    (``CreateManagerStep``/``CreateWaitersStep``/``CreateKitchenStaffStep``)
    take the identical five keyword arguments per their own constructors.
    A typed container (not a ``dict``) so each ``make_*_step`` below can
    pass its fields through as real, individually-typed keyword
    arguments -- ``**a_dict`` unpacking can't be checked against a
    constructor's specific parameter types under mypy strict."""

    create_user_use_case: CreateUserUseCase
    get_role_by_name_use_case: GetRoleByNameUseCase
    assign_user_role_use_case: AssignUserRoleUseCase
    get_user_use_case: GetUserUseCase
    resolve_user_permissions_use_case: ResolveUserPermissionsUseCase


def _make_staff_step_use_cases(
    session_factory: async_sessionmaker[AsyncSession],
) -> _StaffStepUseCases:
    resolve_permissions = make_resolve_user_permissions_use_case(session_factory)
    return _StaffStepUseCases(
        create_user_use_case=CreateUserUseCase(
            session_factory=session_factory,
            user_repository_factory=SQLAlchemyUserRepository,
            password_hasher=make_password_hasher(),
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_role_by_name_use_case=GetRoleByNameUseCase(
            session_factory=session_factory, role_repository_factory=SQLAlchemyRoleRepository
        ),
        assign_user_role_use_case=AssignUserRoleUseCase(
            session_factory=session_factory,
            resolve_user_permissions_use_case=resolve_permissions,
            role_repository_factory=SQLAlchemyRoleRepository,
            role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
            user_role_repository_factory=SQLAlchemyUserRoleRepository,
            user_repository_factory=SQLAlchemyUserRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_user_use_case=GetUserUseCase(
            session_factory=session_factory, user_repository_factory=SQLAlchemyUserRepository
        ),
        resolve_user_permissions_use_case=resolve_permissions,
    )


def make_create_manager_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> CreateManagerStep:
    u = _make_staff_step_use_cases(session_factory)
    return CreateManagerStep(
        create_user_use_case=u.create_user_use_case,
        get_role_by_name_use_case=u.get_role_by_name_use_case,
        assign_user_role_use_case=u.assign_user_role_use_case,
        get_user_use_case=u.get_user_use_case,
        resolve_user_permissions_use_case=u.resolve_user_permissions_use_case,
    )


def make_create_waiters_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> CreateWaitersStep:
    u = _make_staff_step_use_cases(session_factory)
    return CreateWaitersStep(
        create_user_use_case=u.create_user_use_case,
        get_role_by_name_use_case=u.get_role_by_name_use_case,
        assign_user_role_use_case=u.assign_user_role_use_case,
        get_user_use_case=u.get_user_use_case,
        resolve_user_permissions_use_case=u.resolve_user_permissions_use_case,
    )


def make_create_kitchen_staff_step(
    session_factory: async_sessionmaker[AsyncSession],
) -> CreateKitchenStaffStep:
    u = _make_staff_step_use_cases(session_factory)
    return CreateKitchenStaffStep(
        create_user_use_case=u.create_user_use_case,
        get_role_by_name_use_case=u.get_role_by_name_use_case,
        assign_user_role_use_case=u.assign_user_role_use_case,
        get_user_use_case=u.get_user_use_case,
        resolve_user_permissions_use_case=u.resolve_user_permissions_use_case,
    )


def make_create_menu_category_step(session_factory: async_sessionmaker[AsyncSession]) -> CreateMenuCategoryStep:
    return CreateMenuCategoryStep(
        create_menu_category_use_case=CreateMenuCategoryUseCase(
            session_factory=session_factory,
            restaurant_repository_factory=SQLAlchemyRestaurantRepository,
            menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_menu_category_use_case=GetMenuCategoryUseCase(
            session_factory=session_factory,
            menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
        ),
    )


def make_create_menu_items_step(session_factory: async_sessionmaker[AsyncSession]) -> CreateMenuItemsStep:
    return CreateMenuItemsStep(
        create_menu_item_use_case=CreateMenuItemUseCase(
            session_factory=session_factory,
            menu_category_repository_factory=SQLAlchemyMenuCategoryRepository,
            menu_item_repository_factory=SQLAlchemyMenuItemRepository,
            outbox_writer_factory=SQLAlchemyOutboxWriter,
        ),
        get_menu_item_use_case=GetMenuItemUseCase(
            session_factory=session_factory,
            menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        ),
    )


def make_add_inventory_step(session_factory: async_sessionmaker[AsyncSession]) -> AddInventoryStep:
    resolve_permissions = make_resolve_user_permissions_use_case(session_factory)
    return AddInventoryStep(
        create_inventory_category_use_case=CreateInventoryCategoryUseCase(
            session_factory=session_factory,
            inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
            resolve_user_permissions=resolve_permissions,
        ),
        create_inventory_item_use_case=CreateInventoryItemUseCase(
            session_factory=session_factory,
            inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
            inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
            branch_repository_factory=SQLAlchemyBranchRepository,
            resolve_user_permissions=resolve_permissions,
        ),
        get_inventory_item_use_case=GetInventoryItemUseCase(
            session_factory=session_factory,
            inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
            inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
            resolve_user_permissions=resolve_permissions,
        ),
        get_inventory_category_use_case=GetInventoryCategoryUseCase(
            session_factory=session_factory,
            inventory_category_repository_factory=SQLAlchemyInventoryCategoryRepository,
            resolve_user_permissions=resolve_permissions,
        ),
    )


def make_add_recipes_step(session_factory: async_sessionmaker[AsyncSession]) -> AddRecipesStep:
    return AddRecipesStep(
        revise_recipe_use_case=ReviseRecipeUseCase(
            session_factory=session_factory,
            recipe_repository_factory=SQLAlchemyRecipeRepository,
            inventory_item_repository_factory=SQLAlchemyInventoryItemRepository,
            menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        ),
        get_menu_item_recipe_use_case=GetMenuItemRecipeUseCase(
            session_factory=session_factory,
            recipe_repository_factory=SQLAlchemyRecipeRepository,
            menu_item_repository_factory=SQLAlchemyMenuItemRepository,
        ),
    )


# --- ctx fixtures: chain the real prerequisite steps ----------------------


@pytest_asyncio.fixture
async def root_ctx(session_factory: async_sessionmaker[AsyncSession]) -> OnboardingRunContext:
    """Executes the real ``ProvisionTenantStep`` -- the root of the
    graph -- and returns a ctx carrying the real tenant/owner ids every
    other step needs."""
    step = make_provision_tenant_step(session_factory)
    output = await step.execute(
        ProvisionTenantStepInput(
            legal_name="Onboarding Test Co",
            display_name="Onboarding Test",
            default_currency_code="USD",
            owner_email=unique_email("owner"),
        ),
        OnboardingRunContext(),
    )
    return OnboardingRunContext(
        tenant_id=output.tenant_id,
        owner_id=output.owner_id,
        expected_currency_code="USD",
    )


@pytest_asyncio.fixture
async def restaurant_ctx(
    session_factory: async_sessionmaker[AsyncSession], root_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    step = make_create_restaurant_step(session_factory)
    restaurant = await step.execute(
        CreateRestaurantStepInput(
            legal_name="Onboarding Test Restaurant",
            display_name="Test Restaurant",
            default_currency_code="USD",
        ),
        root_ctx,
    )
    return root_ctx.model_copy(update={"restaurant_id": restaurant.id})


@pytest_asyncio.fixture
async def branch_ctx(
    session_factory: async_sessionmaker[AsyncSession], restaurant_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    step = make_create_branch_step(session_factory)
    branch = await step.execute(CreateBranchStepInput(name="Main Branch"), restaurant_ctx)
    return restaurant_ctx.model_copy(update={"branch_id": branch.id})


@pytest_asyncio.fixture
async def table_zone_ctx(
    session_factory: async_sessionmaker[AsyncSession], branch_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    step = make_create_table_zone_step(session_factory)
    zone = await step.execute(CreateTableZoneStepInput(name="Main Dining"), branch_ctx)
    return branch_ctx.model_copy(update={"table_zone_id": zone.id})


@pytest_asyncio.fixture
async def tables_ctx(
    session_factory: async_sessionmaker[AsyncSession], table_zone_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    step = make_create_table_step(session_factory)
    tables = await step.execute(
        CreateTableStepInput(
            tables=[
                TableSpec(table_number="T1", capacity=2),
                TableSpec(table_number="T2", capacity=4),
            ]
        ),
        table_zone_ctx,
    )
    return table_zone_ctx.model_copy(update={"table_ids": tuple(t.id for t in tables)})


@pytest_asyncio.fixture
async def menu_category_ctx(
    session_factory: async_sessionmaker[AsyncSession], branch_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    """Built on top of ``branch_ctx`` (not ``restaurant_ctx``) purely so
    the Catalog-track fixtures below (``menu_items_ctx``,
    ``catalog_with_inventory_ctx``) also carry a real ``branch_id`` --
    ``CreateMenuCategoryStep`` itself only reads ``ctx.restaurant_id``
    (see its own test file, which uses ``restaurant_ctx`` directly to
    prove that independence)."""
    step = make_create_menu_category_step(session_factory)
    category = await step.execute(CreateMenuCategoryStepInput(name="Mains"), branch_ctx)
    return branch_ctx.model_copy(update={"menu_category_id": category.id})


@pytest_asyncio.fixture
async def menu_items_ctx(
    session_factory: async_sessionmaker[AsyncSession], menu_category_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    step = make_create_menu_items_step(session_factory)
    items = await step.execute(
        CreateMenuItemsStepInput(
            items=[
                MenuItemSpec(name="Burger", price_amount=Decimal("9.99"), currency_code="USD"),
                MenuItemSpec(name="Fries", price_amount=Decimal("3.99"), currency_code="USD"),
            ]
        ),
        menu_category_ctx,
    )
    return menu_category_ctx.model_copy(update={"menu_item_ids": tuple(i.id for i in items)})


@pytest_asyncio.fixture
async def catalog_with_inventory_ctx(
    session_factory: async_sessionmaker[AsyncSession], menu_items_ctx: OnboardingRunContext
) -> OnboardingRunContext:
    """``menu_items_ctx`` plus a real ``AddInventoryStep`` execution --
    ``AddRecipesStep`` (``requires=[create_menu_items, add_inventory]``)
    needs both a menu item and an inventory item to already exist."""
    step = make_add_inventory_step(session_factory)
    item = await step.execute(
        AddInventoryStepInput(
            category_name="Produce", category_type="food", item_name="Tomato", unit="kg"
        ),
        menu_items_ctx,
    )
    return menu_items_ctx.model_copy(update={"inventory_item_id": item.id})
