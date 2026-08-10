"""In-memory test doubles for the restaurant module's ports.

Mirrors ``tests.unit.modules.identity.fakes``'s exact convention: these
implement the same ``Protocol`` interfaces the SQLAlchemy repositories
implement, so a use case under test cannot tell the difference and no
real database is ever touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.restaurant.domain.entities import (
    Address,
    Branch,
    MenuCategory,
    MenuItem,
    MenuItemAvailability,
    MenuItemBranchPrice,
    Modifier,
    ModifierGroup,
    OperatingHours,
    QRCode,
    Reservation,
    Restaurant,
    Table,
    TableZone,
)
from restaurant_os_api.platform.events import DomainEvent
from restaurant_os_api.platform.rate_limiting import RateLimitExceededError


class FakeAsyncSession:
    """Stands in for ``AsyncSession`` wherever ``UnitOfWork`` needs one."""

    def __init__(self) -> None:
        self.executed_statements: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def execute(self, statement: object, params: object = None) -> None:
        self.executed_statements.append((statement, params))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


def fake_session_factory_returning(session: FakeAsyncSession):
    """Return a zero-arg callable matching ``async_sessionmaker``'s call shape."""

    def _factory() -> FakeAsyncSession:
        return session

    return _factory


class InMemoryRestaurantRepository:
    def __init__(self, restaurants: dict[str, Restaurant] | None = None) -> None:
        self._restaurants = restaurants or {}

    async def get_by_id(self, tenant_id: str, restaurant_id: str) -> Restaurant | None:
        restaurant = self._restaurants.get(restaurant_id)
        if restaurant is None or restaurant.tenant_id != tenant_id:
            return None
        return restaurant

    async def create(self, restaurant: Restaurant) -> Restaurant:
        self._restaurants[restaurant.id] = restaurant
        return restaurant

    async def update(self, restaurant: Restaurant) -> Restaurant:
        self._restaurants[restaurant.id] = restaurant
        return restaurant

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Restaurant], int]:
        visible = [r for r in self._restaurants.values() if r.tenant_id == tenant_id]
        visible.sort(key=lambda r: r.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)


class InMemoryAddressRepository:
    def __init__(self, addresses: dict[str, Address] | None = None) -> None:
        self._addresses = addresses or {}

    async def get_by_id(self, tenant_id: str, address_id: str) -> Address | None:
        address = self._addresses.get(address_id)
        if address is None or address.tenant_id != tenant_id:
            return None
        return address

    async def create(self, address: Address) -> Address:
        self._addresses[address.id] = address
        return address

    async def update(self, address: Address) -> Address:
        self._addresses[address.id] = address
        return address


class InMemoryBranchRepository:
    def __init__(self, branches: dict[str, Branch] | None = None) -> None:
        self._branches = branches or {}

    async def get_by_id(self, tenant_id: str, branch_id: str) -> Branch | None:
        branch = self._branches.get(branch_id)
        if branch is None or branch.tenant_id != tenant_id:
            return None
        return branch

    async def get_by_restaurant_id_and_name(
        self, tenant_id: str, restaurant_id: str, name: str
    ) -> Branch | None:
        for branch in self._branches.values():
            if (
                branch.tenant_id == tenant_id
                and branch.restaurant_id == restaurant_id
                and branch.name == name
            ):
                return branch
        return None

    async def create(self, branch: Branch) -> Branch:
        self._branches[branch.id] = branch
        return branch

    async def update(self, branch: Branch) -> Branch:
        self._branches[branch.id] = branch
        return branch

    async def list_for_restaurant(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Branch], int]:
        visible = [
            b
            for b in self._branches.values()
            if b.tenant_id == tenant_id and b.restaurant_id == restaurant_id
        ]
        visible.sort(key=lambda b: b.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Branch], int]:
        visible = [b for b in self._branches.values() if b.tenant_id == tenant_id]
        visible.sort(key=lambda b: b.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def list_by_ids(self, tenant_id: str, branch_ids: frozenset[str]) -> list[Branch]:
        return [
            b for b in self._branches.values() if b.tenant_id == tenant_id and b.id in branch_ids
        ]


class InMemoryOperatingHoursRepository:
    def __init__(self, rows: dict[str, list[OperatingHours]] | None = None) -> None:
        # Keyed by branch_id, mirroring the SQLAlchemy repository's own
        # per-branch scoping -- there is no single-row lookup in the
        # Protocol, only whole-branch list/replace.
        self._rows_by_branch: dict[str, list[OperatingHours]] = rows or {}

    async def list_for_branch(self, tenant_id: str, branch_id: str) -> list[OperatingHours]:
        rows = self._rows_by_branch.get(branch_id, [])
        visible = [r for r in rows if r.tenant_id == tenant_id]
        return sorted(visible, key=lambda r: r.day_of_week)

    async def replace_for_branch(
        self, tenant_id: str, branch_id: str, rows: list[OperatingHours]
    ) -> None:
        self._rows_by_branch[branch_id] = list(rows)


class InMemoryTableZoneRepository:
    def __init__(self, table_zones: dict[str, TableZone] | None = None) -> None:
        self._table_zones = table_zones or {}

    async def get_by_id(self, tenant_id: str, table_zone_id: str) -> TableZone | None:
        table_zone = self._table_zones.get(table_zone_id)
        if table_zone is None or table_zone.tenant_id != tenant_id:
            return None
        return table_zone

    async def get_by_branch_id_and_name(
        self, tenant_id: str, branch_id: str, name: str
    ) -> TableZone | None:
        for table_zone in self._table_zones.values():
            if (
                table_zone.tenant_id == tenant_id
                and table_zone.branch_id == branch_id
                and table_zone.name == name
            ):
                return table_zone
        return None

    async def create(self, table_zone: TableZone) -> TableZone:
        self._table_zones[table_zone.id] = table_zone
        return table_zone

    async def update(self, table_zone: TableZone) -> TableZone:
        self._table_zones[table_zone.id] = table_zone
        return table_zone

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[TableZone], int]:
        visible = [
            tz
            for tz in self._table_zones.values()
            if tz.tenant_id == tenant_id and tz.branch_id == branch_id
        ]
        visible.sort(key=lambda tz: tz.display_order)
        return visible[offset : offset + limit], len(visible)


class InMemoryTableRepository:
    def __init__(self, tables: dict[str, Table] | None = None) -> None:
        self._tables = tables or {}

    async def get_by_id(self, tenant_id: str, table_id: str) -> Table | None:
        table = self._tables.get(table_id)
        if table is None or table.tenant_id != tenant_id:
            return None
        return table

    async def get_by_branch_id_and_table_number(
        self, tenant_id: str, branch_id: str, table_number: str
    ) -> Table | None:
        for table in self._tables.values():
            if (
                table.tenant_id == tenant_id
                and table.branch_id == branch_id
                and table.table_number == table_number
            ):
                return table
        return None

    async def create(self, table: Table) -> Table:
        self._tables[table.id] = table
        return table

    async def update(self, table: Table) -> Table:
        self._tables[table.id] = table
        return table

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Table], int]:
        visible = [
            t
            for t in self._tables.values()
            if t.tenant_id == tenant_id and t.branch_id == branch_id
        ]
        visible.sort(key=lambda t: t.table_number)
        return visible[offset : offset + limit], len(visible)

    async def list_for_table_zone(self, tenant_id: str, table_zone_id: str) -> list[Table]:
        return [
            t
            for t in self._tables.values()
            if t.tenant_id == tenant_id and t.table_zone_id == table_zone_id
        ]


class InMemoryMenuCategoryRepository:
    def __init__(self, menu_categories: dict[str, MenuCategory] | None = None) -> None:
        self._menu_categories = menu_categories or {}

    async def get_by_id(self, tenant_id: str, menu_category_id: str) -> MenuCategory | None:
        menu_category = self._menu_categories.get(menu_category_id)
        if menu_category is None or menu_category.tenant_id != tenant_id:
            return None
        return menu_category

    async def get_by_restaurant_id_and_name(
        self, tenant_id: str, restaurant_id: str, name: str
    ) -> MenuCategory | None:
        for menu_category in self._menu_categories.values():
            if (
                menu_category.tenant_id == tenant_id
                and menu_category.restaurant_id == restaurant_id
                and menu_category.name == name
            ):
                return menu_category
        return None

    async def create(self, menu_category: MenuCategory) -> MenuCategory:
        self._menu_categories[menu_category.id] = menu_category
        return menu_category

    async def update(self, menu_category: MenuCategory) -> MenuCategory:
        self._menu_categories[menu_category.id] = menu_category
        return menu_category

    async def list_for_restaurant(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> tuple[list[MenuCategory], int]:
        visible = [
            c
            for c in self._menu_categories.values()
            if c.tenant_id == tenant_id and c.restaurant_id == restaurant_id
        ]
        visible.sort(key=lambda c: c.display_order)
        return visible[offset : offset + limit], len(visible)


class InMemoryMenuItemRepository:
    def __init__(self, menu_items: dict[str, MenuItem] | None = None) -> None:
        self._menu_items = menu_items or {}

    async def get_by_id(self, tenant_id: str, menu_item_id: str) -> MenuItem | None:
        menu_item = self._menu_items.get(menu_item_id)
        if menu_item is None or menu_item.tenant_id != tenant_id:
            return None
        return menu_item

    async def create(self, menu_item: MenuItem) -> MenuItem:
        self._menu_items[menu_item.id] = menu_item
        return menu_item

    async def update(self, menu_item: MenuItem) -> MenuItem:
        self._menu_items[menu_item.id] = menu_item
        return menu_item

    async def list_for_category(
        self, tenant_id: str, menu_category_id: str, *, offset: int, limit: int
    ) -> tuple[list[MenuItem], int]:
        visible = [
            i
            for i in self._menu_items.values()
            if i.tenant_id == tenant_id and i.menu_category_id == menu_category_id
        ]
        visible.sort(key=lambda i: i.display_order)
        return visible[offset : offset + limit], len(visible)


class InMemoryMenuItemBranchPriceRepository:
    def __init__(self, rows: dict[str, MenuItemBranchPrice] | None = None) -> None:
        self._rows = rows or {}

    async def get_by_id(self, tenant_id: str, row_id: str) -> MenuItemBranchPrice | None:
        row = self._rows.get(row_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    async def create(self, row: MenuItemBranchPrice) -> MenuItemBranchPrice:
        self._rows[row.id] = row
        return row

    async def list_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> list[MenuItemBranchPrice]:
        return [
            r
            for r in self._rows.values()
            if r.tenant_id == tenant_id and r.menu_item_id == menu_item_id
        ]


class InMemoryMenuItemAvailabilityRepository:
    def __init__(self, rows: dict[str, MenuItemAvailability] | None = None) -> None:
        self._rows = rows or {}

    async def get_by_id(self, tenant_id: str, row_id: str) -> MenuItemAvailability | None:
        row = self._rows.get(row_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    async def create(self, row: MenuItemAvailability) -> MenuItemAvailability:
        self._rows[row.id] = row
        return row

    async def list_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> list[MenuItemAvailability]:
        return [
            r
            for r in self._rows.values()
            if r.tenant_id == tenant_id and r.menu_item_id == menu_item_id
        ]


class InMemoryModifierGroupRepository:
    def __init__(self, modifier_groups: dict[str, ModifierGroup] | None = None) -> None:
        self._modifier_groups = modifier_groups or {}

    async def get_by_id(self, tenant_id: str, modifier_group_id: str) -> ModifierGroup | None:
        modifier_group = self._modifier_groups.get(modifier_group_id)
        if modifier_group is None or modifier_group.tenant_id != tenant_id:
            return None
        return modifier_group

    async def create(self, modifier_group: ModifierGroup) -> ModifierGroup:
        self._modifier_groups[modifier_group.id] = modifier_group
        return modifier_group

    async def update(self, modifier_group: ModifierGroup) -> ModifierGroup:
        self._modifier_groups[modifier_group.id] = modifier_group
        return modifier_group

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[ModifierGroup], int]:
        visible = [g for g in self._modifier_groups.values() if g.tenant_id == tenant_id]
        visible.sort(key=lambda g: g.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)


class InMemoryModifierRepository:
    def __init__(self, modifiers: dict[str, Modifier] | None = None) -> None:
        self._modifiers = modifiers or {}

    async def get_by_id(self, tenant_id: str, modifier_id: str) -> Modifier | None:
        modifier = self._modifiers.get(modifier_id)
        if modifier is None or modifier.tenant_id != tenant_id:
            return None
        return modifier

    async def create(self, modifier: Modifier) -> Modifier:
        self._modifiers[modifier.id] = modifier
        return modifier

    async def update(self, modifier: Modifier) -> Modifier:
        self._modifiers[modifier.id] = modifier
        return modifier

    async def list_for_group(self, tenant_id: str, modifier_group_id: str) -> list[Modifier]:
        return [
            m
            for m in self._modifiers.values()
            if m.tenant_id == tenant_id and m.modifier_group_id == modifier_group_id
        ]


class InMemoryMenuItemModifierGroupRepository:
    def __init__(self, attachments: dict[str, frozenset[str]] | None = None) -> None:
        # Keyed by menu_item_id -> frozenset of modifier_group_ids.
        self._attachments: dict[str, frozenset[str]] = attachments or {}
        self.replace_calls: list[tuple[str, str, frozenset[str]]] = []

    async def list_modifier_group_ids_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> frozenset[str]:
        return self._attachments.get(menu_item_id, frozenset())

    async def replace_for_menu_item(
        self, tenant_id: str, menu_item_id: str, modifier_group_ids: frozenset[str]
    ) -> None:
        self.replace_calls.append((tenant_id, menu_item_id, modifier_group_ids))
        self._attachments[menu_item_id] = modifier_group_ids


class InMemoryQRCodeRepository:
    def __init__(self, qr_codes: dict[str, QRCode] | None = None) -> None:
        self._qr_codes = qr_codes or {}

    async def get_by_id(self, tenant_id: str, qr_code_id: str) -> QRCode | None:
        qr_code = self._qr_codes.get(qr_code_id)
        if qr_code is None or qr_code.tenant_id != tenant_id:
            return None
        return qr_code

    async def get_by_token(self, token: str) -> QRCode | None:
        for qr_code in self._qr_codes.values():
            if qr_code.token == token:
                return qr_code
        return None

    async def create(self, qr_code: QRCode) -> QRCode:
        self._qr_codes[qr_code.id] = qr_code
        return qr_code

    async def update(self, qr_code: QRCode) -> QRCode:
        self._qr_codes[qr_code.id] = qr_code
        return qr_code

    async def list_for_table(self, tenant_id: str, table_id: str) -> list[QRCode]:
        visible = [
            c
            for c in self._qr_codes.values()
            if c.tenant_id == tenant_id and c.table_id == table_id
        ]
        visible.sort(key=lambda c: c.created_at, reverse=True)
        return visible


class InMemoryReservationRepository:
    def __init__(self, reservations: dict[str, Reservation] | None = None) -> None:
        self._reservations = reservations or {}

    async def get_by_id(self, tenant_id: str, reservation_id: str) -> Reservation | None:
        reservation = self._reservations.get(reservation_id)
        if reservation is None or reservation.tenant_id != tenant_id:
            return None
        return reservation

    async def create(self, reservation: Reservation) -> Reservation:
        self._reservations[reservation.id] = reservation
        return reservation

    async def update(self, reservation: Reservation) -> Reservation:
        self._reservations[reservation.id] = reservation
        return reservation

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Reservation], int]:
        visible = [
            r
            for r in self._reservations.values()
            if r.tenant_id == tenant_id and r.branch_id == branch_id
        ]
        visible.sort(key=lambda r: r.requested_at)
        return visible[offset : offset + limit], len(visible)


@dataclass
class FakeResolveUserPermissionsUseCase:
    """Returns a fixed ``ResolvedPermissions`` regardless of input --
    enough for unit-testing callers that only need *some* resolved
    grant, not the full RBAC resolution pipeline (that has its own
    dedicated test suite in ``modules.identity``)."""

    resolved: ResolvedPermissions = field(default_factory=ResolvedPermissions)

    async def execute(self, tenant_id: str, user_id: str) -> ResolvedPermissions:
        return self.resolved


@dataclass
class FakeQRResolutionRateLimiter:
    """Records every ``check``/``record_failure`` call; raises
    ``RateLimitExceededError`` when told to, for testing
    ``ResolveQRCodeUseCase``'s own handling of that exception without a
    real Postgres-backed counter table."""

    raise_on_check: bool = False
    raise_on_record_failure: bool = False
    check_calls: list[tuple[str, str]] = field(default_factory=list)
    record_failure_calls: list[tuple[str, str]] = field(default_factory=list)

    async def check(self, *, source_ip: str, token: str) -> None:
        self.check_calls.append((source_ip, token))
        if self.raise_on_check:
            raise RateLimitExceededError()

    async def record_failure(self, *, source_ip: str, token: str) -> None:
        self.record_failure_calls.append((source_ip, token))
        if self.raise_on_record_failure:
            raise RateLimitExceededError()


@dataclass
class FakeOutboxWriter:
    """Records every published event in order; never touches a database."""

    published: list[tuple[str, DomainEvent]] = field(default_factory=list)

    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        self.published.append((tenant_id, event))
