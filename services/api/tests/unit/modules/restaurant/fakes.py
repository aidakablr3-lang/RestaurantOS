"""In-memory test doubles for the restaurant module's ports.

Mirrors ``tests.unit.modules.identity.fakes``'s exact convention: these
implement the same ``Protocol`` interfaces the SQLAlchemy repositories
implement, so a use case under test cannot tell the difference and no
real database is ever touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from restaurant_os_api.modules.restaurant.domain.entities import Restaurant
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


@dataclass
class FakeOutboxWriter:
    """Records every published event in order; never touches a database."""

    published: list[tuple[str, DomainEvent]] = field(default_factory=list)

    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        self.published.append((tenant_id, event))
