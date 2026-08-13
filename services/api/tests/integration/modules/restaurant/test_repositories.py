"""Integration tests for the restaurant module's repositories, real Row-
Level Security, and real database constraints (Restaurant Platform
Architecture SS4/SS9/SS13, Sprint 5 Step 3).

Requires TEST_DATABASE_URL (see tests/integration/conftest.py). Follows
test_repositories.py's and test_rbac_repositories.py's own pattern
exactly: cross-tenant tests issue a deliberately unfiltered raw query,
proving the database *policy* blocks the row, independent of any
repository-level filter.

**Two disclosed, real findings from writing this suite** (not silently
fixed -- Step 3 is data-layer only, and inventing new constraints
beyond what the approved architecture specifies is exactly the kind of
unrequested change this step's instructions warn against):

1. No trigger enforces that a branch-scoped child row's ``branch_id``
   actually belongs to the same tenant as its own ``tenant_id`` (the
   same *shape* of "confused deputy" gap RBAC's ``user_roles.branch_id``
   had before migration 0004 closed it for that one case) -- e.g.
   nothing stops constructing a ``Table`` whose ``table_zone_id`` points
   at a ``TableZone`` in a *different* branch than the ``Table``'s own
   ``branch_id``. Restaurant Platform Architecture SS4.4 establishes
   branch-level consistency as an application-layer concern by design
   (for the *access* question -- who may act on which branch), but does
   not explicitly extend that reasoning to *referential* consistency
   between sibling branch-scoped columns, and no trigger for it is
   specified anywhere in SS9's DDL. `test_table_zone_and_branch_id_consistency_is_not_currently_enforced_by_the_database`
   proves this gap exists today, as a known limitation for the final
   report, not a bug quietly patched in this commit.
2. Similarly, nothing stops a ``Branch`` from being created with a
   ``restaurant_id`` that belongs to a *different tenant* than the
   ``Branch``'s own ``tenant_id`` -- the FK only checks that the
   referenced restaurant row exists somewhere, not that it belongs to
   the same tenant. RLS makes this unreachable through any tenant-
   scoped *read* path (a caller can never see another tenant's
   restaurant to reference it), but a raw, privileged write (as this
   test performs, matching how the RLS-proof tests in this file also
   deliberately bypass the ORM) can still construct it. Documented, not
   fixed, by the same reasoning as (1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.domain.entities import Tenant, TenantStatus, TenantTier
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyTenantRepository,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuCategory,
    MenuItem,
    MenuItemAvailability,
    MenuItemBranchPrice,
    Modifier,
    ModifierGroup,
    ModifierSelectionType,
    QRCode,
    QRCodeStatus,
    Reservation,
    ReservationStatus,
    Restaurant,
    RestaurantStatus,
    Table,
    TableStatus,
    TableZone,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.repositories import (
    SQLAlchemyBranchRepository,
    SQLAlchemyMenuCategoryRepository,
    SQLAlchemyMenuItemAvailabilityRepository,
    SQLAlchemyMenuItemBranchPriceRepository,
    SQLAlchemyMenuItemModifierGroupRepository,
    SQLAlchemyMenuItemRepository,
    SQLAlchemyModifierGroupRepository,
    SQLAlchemyModifierRepository,
    SQLAlchemyQRCodeRepository,
    SQLAlchemyReservationRepository,
    SQLAlchemyRestaurantRepository,
    SQLAlchemyTableRepository,
    SQLAlchemyTableZoneRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

NOW = datetime.now(UTC)


async def _create_tenant(session_factory, **overrides) -> Tenant:
    tenant = Tenant(
        id=generate_ulid(),
        legal_name=overrides.get("legal_name", "Acme Restaurants Inc."),
        display_name=overrides.get("display_name", "Acme"),
        tenant_tier=TenantTier.SHARED,
        status=overrides.get("status", TenantStatus.ACTIVE),
        default_currency_code="USD",
        created_at=NOW,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
        repo = SQLAlchemyTenantRepository(uow.session)
        await repo.create(tenant)
    return tenant


async def _create_restaurant(session_factory, tenant_id: str, **overrides) -> Restaurant:
    restaurant = Restaurant(
        id=generate_ulid(),
        tenant_id=tenant_id,
        legal_name=overrides.get("legal_name", "Acme Diner LLC"),
        display_name=overrides.get("display_name", "Acme Diner"),
        default_currency_code="USD",
        status=RestaurantStatus.ACTIVE,
        created_at=NOW,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyRestaurantRepository(uow.session)
        return await repo.create(restaurant)


async def _create_branch(
    session_factory, tenant_id: str, restaurant_id: str, **overrides
) -> Branch:
    branch = Branch(
        id=generate_ulid(),
        tenant_id=tenant_id,
        restaurant_id=restaurant_id,
        name=overrides.get("name", "Main Street"),
        status=BranchStatus.ACTIVE,
        created_at=NOW,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyBranchRepository(uow.session)
        return await repo.create(branch)


async def _create_table_zone(
    session_factory, tenant_id: str, branch_id: str, **overrides
) -> TableZone:
    zone = TableZone(
        id=generate_ulid(),
        tenant_id=tenant_id,
        branch_id=branch_id,
        name=overrides.get("name", "Patio"),
        display_order=0,
        created_at=NOW,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyTableZoneRepository(uow.session)
        return await repo.create(zone)


async def _create_menu_category(
    session_factory, tenant_id: str, restaurant_id: str, **overrides
) -> MenuCategory:
    category = MenuCategory(
        id=generate_ulid(),
        tenant_id=tenant_id,
        restaurant_id=restaurant_id,
        name=overrides.get("name", "Entrees"),
        display_order=0,
        created_at=NOW,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyMenuCategoryRepository(uow.session)
        return await repo.create(category)


async def _create_menu_item(
    session_factory, tenant_id: str, menu_category_id: str, **overrides
) -> MenuItem:
    item = MenuItem(
        id=generate_ulid(),
        tenant_id=tenant_id,
        menu_category_id=menu_category_id,
        name=overrides.get("name", "Cheeseburger"),
        price_amount=Decimal(overrides.get("price_amount", "12.5000")),
        currency_code="USD",
        is_available=True,
        display_order=0,
        created_at=NOW,
    )
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        repo = SQLAlchemyMenuItemRepository(uow.session)
        return await repo.create(item)


class TestRestaurantRepository:
    async def test_create_and_get_by_id(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRestaurantRepository(uow.session)
            found = await repo.get_by_id(tenant.id, restaurant.id)

        assert found is not None
        assert found.legal_name == "Acme Diner LLC"
        assert found.status == RestaurantStatus.ACTIVE

    async def test_list_for_tenant_paginates_and_counts(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        for i in range(3):
            await _create_restaurant(session_factory, tenant.id, legal_name=f"Diner {i} LLC")

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRestaurantRepository(uow.session)
            page, total = await repo.list_for_tenant(tenant.id, offset=0, limit=2)

        assert total == 3
        assert len(page) == 2

    async def test_soft_deleted_restaurant_excluded_from_get_by_id(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await uow.session.execute(
                text("UPDATE restaurants SET deleted_at = now() WHERE id = :id"),
                {"id": restaurant.id},
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyRestaurantRepository(uow.session)
            assert await repo.get_by_id(tenant.id, restaurant.id) is None

        # The row itself still exists (soft delete, not hard delete) --
        # for historical referential integrity, matching every other
        # SoftDeleteMixin entity in this codebase.
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            still_there = await uow.session.execute(
                text("SELECT deleted_at FROM restaurants WHERE id = :id"), {"id": restaurant.id}
            )
            row = still_there.one()
            assert row.deleted_at is not None

    async def test_row_level_security_blocks_cross_tenant_restaurant_reads(
        self, session_factory
    ) -> None:
        """Restaurant Platform's own version of the "single most
        important test" this suite's precedents establish -- a
        deliberately unfiltered raw query proving RLS, not application
        code, hides another tenant's row."""
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        await _create_restaurant(session_factory, tenant_a.id, legal_name="Tenant A Diner")
        await _create_restaurant(session_factory, tenant_b.id, legal_name="Tenant B Diner")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            result = await uow.session.execute(
                text("SELECT tenant_id, legal_name FROM restaurants")
            )
            rows = result.all()

        assert len(rows) == 1, "RLS must hide every row outside the current tenant context"
        assert rows[0].tenant_id == tenant_a.id
        assert rows[0].legal_name == "Tenant A Diner"


class TestBranchRepository:
    async def test_create_and_get_by_id(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyBranchRepository(uow.session)
            found = await repo.get_by_id(tenant.id, branch.id)

        assert found is not None
        assert found.restaurant_id == restaurant.id

    async def test_duplicate_name_within_the_same_restaurant_raises_integrity_error(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        await _create_branch(session_factory, tenant.id, restaurant.id, name="Downtown")

        with pytest.raises(IntegrityError):
            await _create_branch(session_factory, tenant.id, restaurant.id, name="Downtown")

    async def test_the_same_name_is_allowed_across_different_restaurants(
        self, session_factory
    ) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant_a = await _create_restaurant(
            session_factory, tenant.id, legal_name="Brand A LLC"
        )
        restaurant_b = await _create_restaurant(
            session_factory, tenant.id, legal_name="Brand B LLC"
        )

        branch_a = await _create_branch(
            session_factory, tenant.id, restaurant_a.id, name="Downtown"
        )
        branch_b = await _create_branch(
            session_factory, tenant.id, restaurant_b.id, name="Downtown"
        )
        assert branch_a.id != branch_b.id

    async def test_row_level_security_blocks_cross_tenant_branch_reads(
        self, session_factory
    ) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        restaurant_a = await _create_restaurant(session_factory, tenant_a.id)
        restaurant_b = await _create_restaurant(session_factory, tenant_b.id)
        await _create_branch(session_factory, tenant_a.id, restaurant_a.id, name="Tenant A Branch")
        await _create_branch(session_factory, tenant_b.id, restaurant_b.id, name="Tenant B Branch")

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            result = await uow.session.execute(text("SELECT tenant_id, name FROM branches"))
            rows = result.all()

        assert len(rows) == 1
        assert rows[0].tenant_id == tenant_a.id
        assert rows[0].name == "Tenant A Branch"

    async def test_deleting_a_restaurant_with_a_branch_is_restricted(self, session_factory) -> None:
        """ON DELETE RESTRICT on branches.restaurant_id (Restaurant
        Platform Architecture SS9.4): a Restaurant with any Branch
        cannot be hard-deleted -- soft-delete is the retirement path."""
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        await _create_branch(session_factory, tenant.id, restaurant.id)

        with pytest.raises(IntegrityError):
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                await uow.session.execute(
                    text("DELETE FROM restaurants WHERE id = :id"), {"id": restaurant.id}
                )

    async def test_a_branch_referencing_a_different_tenants_restaurant_is_not_currently_rejected(
        self, session_factory
    ) -> None:
        """**Disclosed finding (2), not fixed in this step**: the FK on
        branches.restaurant_id only checks the referenced row exists,
        not that it belongs to the same tenant. This deliberately
        bypasses the normal tenant-scoped write path (which could never
        construct this in practice, since tenant A cannot even see
        tenant B's restaurant under RLS) to prove the schema itself has
        no independent guard, the same way the RLS proof tests above
        deliberately bypass application code to test the database
        directly."""
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        restaurant_b = await _create_restaurant(session_factory, tenant_b.id)

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            # Deliberately raw: tenant_id=tenant_a, but restaurant_id
            # belongs to tenant_b.
            await uow.session.execute(
                text(
                    "INSERT INTO branches (id, tenant_id, restaurant_id, name) "
                    "VALUES (:id, :tenant_id, :restaurant_id, 'Cross Tenant Branch')"
                ),
                {"id": generate_ulid(), "tenant_id": tenant_a.id, "restaurant_id": restaurant_b.id},
            )
            # Must not raise -- this is the gap being documented, not tested-as-fixed.


class TestTableZoneRepository:
    async def test_create_and_uniqueness(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)
        await _create_table_zone(session_factory, tenant.id, branch.id, name="Patio")

        with pytest.raises(IntegrityError):
            await _create_table_zone(session_factory, tenant.id, branch.id, name="Patio")

    async def test_list_for_branch_only_returns_that_branchs_zones(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch_a = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch A")
        branch_b = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch B")
        await _create_table_zone(session_factory, tenant.id, branch_a.id, name="Patio")
        await _create_table_zone(session_factory, tenant.id, branch_b.id, name="Bar")

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyTableZoneRepository(uow.session)
            zones, total = await repo.list_for_branch(tenant.id, branch_a.id, offset=0, limit=10)

        assert total == 1
        assert zones[0].name == "Patio"


class TestTableRepository:
    async def test_create_and_uniqueness(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)
        zone = await _create_table_zone(session_factory, tenant.id, branch.id)

        table = Table(
            id=generate_ulid(),
            tenant_id=tenant.id,
            branch_id=branch.id,
            table_zone_id=zone.id,
            table_number="12A",
            capacity=4,
            status=TableStatus.AVAILABLE,
            sync_version=0,
            created_at=NOW,
        )
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyTableRepository(uow.session)
            await repo.create(table)

        with pytest.raises(IntegrityError):
            duplicate = Table(
                id=generate_ulid(),
                tenant_id=tenant.id,
                branch_id=branch.id,
                table_zone_id=zone.id,
                table_number="12A",
                capacity=2,
                status=TableStatus.AVAILABLE,
                sync_version=0,
                created_at=NOW,
            )
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                repo = SQLAlchemyTableRepository(uow.session)
                await repo.create(duplicate)

    async def test_capacity_must_be_positive(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)
        zone = await _create_table_zone(session_factory, tenant.id, branch.id)

        with pytest.raises(IntegrityError):
            table = Table(
                id=generate_ulid(),
                tenant_id=tenant.id,
                branch_id=branch.id,
                table_zone_id=zone.id,
                table_number="1",
                capacity=0,
                status=TableStatus.AVAILABLE,
                sync_version=0,
                created_at=NOW,
            )
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                repo = SQLAlchemyTableRepository(uow.session)
                await repo.create(table)

    async def test_branch_isolation_list_for_branch_never_returns_another_branchs_tables(
        self, session_factory
    ) -> None:
        """Data-layer branch isolation: a repository query scoped to one
        branch never returns another branch's rows, even within the
        same tenant. This is a correctness property of the query itself
        -- it is *not* the same thing as role-based authorization
        ("can this specific user act on this branch"), which is Step
        4/5's RBAC-integration concern and does not exist at this data
        layer yet."""
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch_a = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch A")
        branch_b = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch B")
        zone_a = await _create_table_zone(session_factory, tenant.id, branch_a.id)
        zone_b = await _create_table_zone(session_factory, tenant.id, branch_b.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyTableRepository(uow.session)
            await repo.create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch_a.id,
                    table_zone_id=zone_a.id,
                    table_number="1",
                    capacity=2,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=NOW,
                )
            )
            await repo.create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch_b.id,
                    table_zone_id=zone_b.id,
                    table_number="1",
                    capacity=2,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyTableRepository(uow.session)
            tables, total = await repo.list_for_branch(tenant.id, branch_a.id, offset=0, limit=10)

        assert total == 1
        assert tables[0].branch_id == branch_a.id

    async def test_table_zone_and_branch_id_consistency_is_not_currently_enforced_by_the_database(
        self, session_factory
    ) -> None:
        """**Disclosed finding (1)** -- see module docstring. Proves,
        rather than assumes, that a Table can currently be created with
        a table_zone_id belonging to a *different* branch than the
        Table's own branch_id, with no database-level rejection."""
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch_a = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch A")
        branch_b = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch B")
        zone_in_branch_b = await _create_table_zone(session_factory, tenant.id, branch_b.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyTableRepository(uow.session)
            # branch_id=branch_a, but table_zone_id belongs to branch_b.
            mismatched = await repo.create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch_a.id,
                    table_zone_id=zone_in_branch_b.id,
                    table_number="1",
                    capacity=2,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=NOW,
                )
            )
        # Must not raise -- this is the gap being documented, not tested-as-fixed.
        assert mismatched.table_zone_id == zone_in_branch_b.id


class TestQRCodeRepository:
    async def test_create_and_get_by_token(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)
        zone = await _create_table_zone(session_factory, tenant.id, branch.id)
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            table = await SQLAlchemyTableRepository(uow.session).create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch.id,
                    table_zone_id=zone.id,
                    table_number="1",
                    capacity=2,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=NOW,
                )
            )

        qr = QRCode(
            id=generate_ulid(),
            tenant_id=tenant.id,
            branch_id=branch.id,
            table_id=table.id,
            token="opaque-token-abc123",
            status=QRCodeStatus.ACTIVE,
            created_at=NOW,
        )
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await SQLAlchemyQRCodeRepository(uow.session).create(qr)

        # Token resolution is deliberately NOT tenant-scoped (the guest-
        # resolution path, Restaurant Platform Architecture SS3.1).
        async with UnitOfWork(session_factory) as uow:
            found = await SQLAlchemyQRCodeRepository(uow.session).get_by_token(
                "opaque-token-abc123"
            )
        assert found is not None
        assert found.table_id == table.id

    async def test_token_uniqueness_is_global(self, session_factory) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        restaurant_a = await _create_restaurant(session_factory, tenant_a.id)
        restaurant_b = await _create_restaurant(session_factory, tenant_b.id)
        branch_a = await _create_branch(session_factory, tenant_a.id, restaurant_a.id)
        branch_b = await _create_branch(session_factory, tenant_b.id, restaurant_b.id)
        zone_a = await _create_table_zone(session_factory, tenant_a.id, branch_a.id)
        zone_b = await _create_table_zone(session_factory, tenant_b.id, branch_b.id)

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            table_a = await SQLAlchemyTableRepository(uow.session).create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant_a.id,
                    branch_id=branch_a.id,
                    table_zone_id=zone_a.id,
                    table_number="1",
                    capacity=2,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=NOW,
                )
            )
            await SQLAlchemyQRCodeRepository(uow.session).create(
                QRCode(
                    id=generate_ulid(),
                    tenant_id=tenant_a.id,
                    branch_id=branch_a.id,
                    table_id=table_a.id,
                    token="shared-token",
                    status=QRCodeStatus.ACTIVE,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant_b.id)) as uow:
            table_b = await SQLAlchemyTableRepository(uow.session).create(
                Table(
                    id=generate_ulid(),
                    tenant_id=tenant_b.id,
                    branch_id=branch_b.id,
                    table_zone_id=zone_b.id,
                    table_number="1",
                    capacity=2,
                    status=TableStatus.AVAILABLE,
                    sync_version=0,
                    created_at=NOW,
                )
            )

        # A separate UnitOfWork, deliberately: once a flush fails inside
        # a session, that session's transaction is unusable for further
        # statements (including the commit UnitOfWork.__aexit__ would
        # otherwise issue) until it's rolled back -- so the failing
        # insert must be the *only* statement in its own transaction,
        # with pytest.raises wrapping the whole `async with` block, not
        # nested inside an otherwise-successful one.
        with pytest.raises(IntegrityError):
            async with UnitOfWork(session_factory, TenantContext(tenant_b.id)) as uow:
                await SQLAlchemyQRCodeRepository(uow.session).create(
                    QRCode(
                        id=generate_ulid(),
                        tenant_id=tenant_b.id,
                        branch_id=branch_b.id,
                        table_id=table_b.id,
                        token="shared-token",
                        status=QRCodeStatus.ACTIVE,
                        created_at=NOW,
                    )
                )


class TestMenuCategoryAndMenuItemRepository:
    async def test_menu_category_create_and_uniqueness(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        await _create_menu_category(session_factory, tenant.id, restaurant.id, name="Entrees")

        with pytest.raises(IntegrityError):
            await _create_menu_category(session_factory, tenant.id, restaurant.id, name="Entrees")

    async def test_menu_item_creation_and_price_non_negative(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        category = await _create_menu_category(session_factory, tenant.id, restaurant.id)
        item = await _create_menu_item(
            session_factory, tenant.id, category.id, price_amount="9.9900"
        )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            found = await SQLAlchemyMenuItemRepository(uow.session).get_by_id(tenant.id, item.id)
        assert found is not None
        assert found.price_amount == item.price_amount

        with pytest.raises(IntegrityError):
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                await SQLAlchemyMenuItemRepository(uow.session).create(
                    MenuItem(
                        id=generate_ulid(),
                        tenant_id=tenant.id,
                        menu_category_id=category.id,
                        name="Free Item",
                        price_amount=Decimal("-1.0000"),
                        currency_code="USD",
                        is_available=True,
                        display_order=0,
                        created_at=NOW,
                    )
                )

    async def test_list_for_category_paginates(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        category = await _create_menu_category(session_factory, tenant.id, restaurant.id)
        for i in range(3):
            await _create_menu_item(session_factory, tenant.id, category.id, name=f"Item {i}")

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            items, total = await SQLAlchemyMenuItemRepository(uow.session).list_for_category(
                tenant.id, category.id, offset=0, limit=2
            )
        assert total == 3
        assert len(items) == 2


class TestMenuItemBranchPriceRepository:
    async def test_branch_specific_pricing(self, session_factory) -> None:
        """The one mechanism Restaurant Platform needs for branch-
        specific pricing (Restaurant Platform Architecture SS6) -- two
        branches, two different override prices for the same item."""
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch_a = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch A")
        branch_b = await _create_branch(session_factory, tenant.id, restaurant.id, name="Branch B")
        category = await _create_menu_category(session_factory, tenant.id, restaurant.id)
        item = await _create_menu_item(
            session_factory, tenant.id, category.id, price_amount="10.0000"
        )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyMenuItemBranchPriceRepository(uow.session)
            await repo.create(
                MenuItemBranchPrice(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch_a.id,
                    menu_item_id=item.id,
                    price_amount=Decimal("11.5000"),
                    effective_from=NOW,
                    created_at=NOW,
                )
            )
            await repo.create(
                MenuItemBranchPrice(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch_b.id,
                    menu_item_id=item.id,
                    price_amount=Decimal("8.7500"),
                    effective_from=NOW,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyMenuItemBranchPriceRepository(uow.session)
            rows = await repo.list_for_menu_item(tenant.id, item.id)

        prices_by_branch = {row.branch_id: row.price_amount for row in rows}
        assert prices_by_branch[branch_a.id] != prices_by_branch[branch_b.id]

    async def test_effective_window_check_constraint(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)
        category = await _create_menu_category(session_factory, tenant.id, restaurant.id)
        item = await _create_menu_item(session_factory, tenant.id, category.id)

        with pytest.raises(IntegrityError):
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                await SQLAlchemyMenuItemBranchPriceRepository(uow.session).create(
                    MenuItemBranchPrice(
                        id=generate_ulid(),
                        tenant_id=tenant.id,
                        branch_id=branch.id,
                        menu_item_id=item.id,
                        price_amount=Decimal("5.0000"),
                        effective_from=NOW,
                        effective_to=NOW - timedelta(days=1),
                        created_at=NOW,
                    )
                )


class TestMenuItemAvailabilityRepository:
    async def test_open_ended_86(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)
        category = await _create_menu_category(session_factory, tenant.id, restaurant.id)
        item = await _create_menu_item(session_factory, tenant.id, category.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await SQLAlchemyMenuItemAvailabilityRepository(uow.session).create(
                MenuItemAvailability(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch.id,
                    menu_item_id=item.id,
                    is_available=False,
                    effective_from=NOW,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            rows = await SQLAlchemyMenuItemAvailabilityRepository(uow.session).list_for_menu_item(
                tenant.id, item.id
            )
        assert len(rows) == 1
        assert rows[0].is_available is False
        assert rows[0].effective_to is None


class TestModifierRelationships:
    async def test_modifier_group_and_modifier_creation(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            group = await SQLAlchemyModifierGroupRepository(uow.session).create(
                ModifierGroup(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    name="Size",
                    selection_type=ModifierSelectionType.SINGLE,
                    created_at=NOW,
                )
            )
            await SQLAlchemyModifierRepository(uow.session).create(
                Modifier(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    modifier_group_id=group.id,
                    name="Large",
                    created_at=NOW,
                    price_delta=Decimal("2.0000"),
                )
            )
            await SQLAlchemyModifierRepository(uow.session).create(
                Modifier(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    modifier_group_id=group.id,
                    name="Small",
                    created_at=NOW,
                    price_delta=Decimal("0.0000"),
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            modifiers = await SQLAlchemyModifierRepository(uow.session).list_for_group(
                tenant.id, group.id
            )
        assert {m.name for m in modifiers} == {"Large", "Small"}

    async def test_the_same_group_name_is_allowed_to_repeat(self, session_factory) -> None:
        """Deliberately no uniqueness constraint on ModifierGroup.name
        (Restaurant Platform Architecture SS3.1) -- "Size" legitimately
        repeats across unrelated item families."""
        tenant = await _create_tenant(session_factory)
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            group_a = await SQLAlchemyModifierGroupRepository(uow.session).create(
                ModifierGroup(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    name="Size",
                    selection_type=ModifierSelectionType.SINGLE,
                    created_at=NOW,
                )
            )
            group_b = await SQLAlchemyModifierGroupRepository(uow.session).create(
                ModifierGroup(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    name="Size",
                    selection_type=ModifierSelectionType.SINGLE,
                    created_at=NOW,
                )
            )
        assert group_a.id != group_b.id

    async def test_menu_item_modifier_group_replace_is_atomic(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        category = await _create_menu_category(session_factory, tenant.id, restaurant.id)
        item = await _create_menu_item(session_factory, tenant.id, category.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            group_a = await SQLAlchemyModifierGroupRepository(uow.session).create(
                ModifierGroup(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    name="Size",
                    selection_type=ModifierSelectionType.SINGLE,
                    created_at=NOW,
                )
            )
            group_b = await SQLAlchemyModifierGroupRepository(uow.session).create(
                ModifierGroup(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    name="Toppings",
                    selection_type=ModifierSelectionType.MULTIPLE,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyMenuItemModifierGroupRepository(uow.session)
            await repo.replace_for_menu_item(
                tenant.id, item.id, frozenset({group_a.id, group_b.id})
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyMenuItemModifierGroupRepository(uow.session)
            ids = await repo.list_modifier_group_ids_for_menu_item(tenant.id, item.id)
        assert ids == frozenset({group_a.id, group_b.id})

        # Replace with just group_a -- group_b must be gone, matching
        # RolePermissionRepository.replace_for_role's own full-replace
        # semantics.
        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyMenuItemModifierGroupRepository(uow.session)
            await repo.replace_for_menu_item(tenant.id, item.id, frozenset({group_a.id}))

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            repo = SQLAlchemyMenuItemModifierGroupRepository(uow.session)
            ids = await repo.list_modifier_group_ids_for_menu_item(tenant.id, item.id)
        assert ids == frozenset({group_a.id})


class TestReservationRepository:
    async def test_create_and_list_for_branch(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            await SQLAlchemyReservationRepository(uow.session).create(
                Reservation(
                    id=generate_ulid(),
                    tenant_id=tenant.id,
                    branch_id=branch.id,
                    party_size=4,
                    requested_at=NOW,
                    status=ReservationStatus.REQUESTED,
                    sync_version=0,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
            reservations, total = await SQLAlchemyReservationRepository(
                uow.session
            ).list_for_branch(tenant.id, branch.id, offset=0, limit=10)
        assert total == 1
        assert reservations[0].party_size == 4
        assert reservations[0].status == ReservationStatus.REQUESTED

    async def test_party_size_must_be_positive(self, session_factory) -> None:
        tenant = await _create_tenant(session_factory)
        restaurant = await _create_restaurant(session_factory, tenant.id)
        branch = await _create_branch(session_factory, tenant.id, restaurant.id)

        with pytest.raises(IntegrityError):
            async with UnitOfWork(session_factory, TenantContext(tenant.id)) as uow:
                await SQLAlchemyReservationRepository(uow.session).create(
                    Reservation(
                        id=generate_ulid(),
                        tenant_id=tenant.id,
                        branch_id=branch.id,
                        party_size=0,
                        requested_at=NOW,
                        status=ReservationStatus.REQUESTED,
                        sync_version=0,
                        created_at=NOW,
                    )
                )

    async def test_row_level_security_blocks_cross_tenant_reservation_reads(
        self, session_factory
    ) -> None:
        tenant_a = await _create_tenant(session_factory, legal_name="Tenant A")
        tenant_b = await _create_tenant(session_factory, legal_name="Tenant B")
        restaurant_a = await _create_restaurant(session_factory, tenant_a.id)
        restaurant_b = await _create_restaurant(session_factory, tenant_b.id)
        branch_a = await _create_branch(session_factory, tenant_a.id, restaurant_a.id)
        branch_b = await _create_branch(session_factory, tenant_b.id, restaurant_b.id)

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            await SQLAlchemyReservationRepository(uow.session).create(
                Reservation(
                    id=generate_ulid(),
                    tenant_id=tenant_a.id,
                    branch_id=branch_a.id,
                    party_size=2,
                    requested_at=NOW,
                    status=ReservationStatus.REQUESTED,
                    sync_version=0,
                    created_at=NOW,
                )
            )
        async with UnitOfWork(session_factory, TenantContext(tenant_b.id)) as uow:
            await SQLAlchemyReservationRepository(uow.session).create(
                Reservation(
                    id=generate_ulid(),
                    tenant_id=tenant_b.id,
                    branch_id=branch_b.id,
                    party_size=6,
                    requested_at=NOW,
                    status=ReservationStatus.REQUESTED,
                    sync_version=0,
                    created_at=NOW,
                )
            )

        async with UnitOfWork(session_factory, TenantContext(tenant_a.id)) as uow:
            result = await uow.session.execute(
                text("SELECT tenant_id, party_size FROM reservations")
            )
            rows = result.all()

        assert len(rows) == 1
        assert rows[0].tenant_id == tenant_a.id
        assert rows[0].party_size == 2
