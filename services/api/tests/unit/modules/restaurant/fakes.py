"""In-memory test doubles for the restaurant module's ports.

Mirrors ``tests.unit.modules.identity.fakes``'s exact convention: these
implement the same ``Protocol`` interfaces the SQLAlchemy repositories
implement, so a use case under test cannot tell the difference and no
real database is ever touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from restaurant_os_api.modules.restaurant.domain.entities import Address, Branch, Restaurant
from restaurant_os_api.platform.events import DomainEvent


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


@dataclass
class FakeOutboxWriter:
    """Records every published event in order; never touches a database."""

    published: list[tuple[str, DomainEvent]] = field(default_factory=list)

    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        self.published.append((tenant_id, event))
