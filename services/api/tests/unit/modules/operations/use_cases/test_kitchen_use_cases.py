"""Unit tests for Kitchen use cases (Sprint 7 Step 3) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    ChangeKitchenItemStatusRequestDTO,
    ChangeKitchenTicketStatusRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    ListKitchenTicketsUseCase,
    UpdateKitchenItemStatusUseCase,
    UpdateKitchenTicketStatusUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItem,
    KitchenItemStatus,
    KitchenTicket,
    KitchenTicketStatus,
    Order,
    OrderSource,
    OrderStatus,
)
from restaurant_os_api.modules.operations.domain.events import TicketReady
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidKitchenItemStatusTransitionError,
    KitchenItemNotFoundError,
    KitchenTicketNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import Branch, BranchStatus
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryKitchenTicketRepository,
    InMemoryOrderRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
ORDER_ID = "01ARZ3NDEKTSV4RRFFQ6ORDR01"
TICKET_ID = "01ARZ3NDEKTSV4RRFFQ6TKT001"
ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6KITM01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": "restaurant-1",
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _order(**overrides) -> Order:
    defaults = {
        "id": ORDER_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "order_source": OrderSource.POS,
        "status": OrderStatus.FIRED,
        "subtotal_amount": Decimal(10),
        "tax_amount": Decimal(0),
        "currency_code": "USD",
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Order(**defaults)


def _ticket(**overrides) -> KitchenTicket:
    defaults = {
        "id": TICKET_ID,
        "tenant_id": TENANT_ID,
        "order_id": ORDER_ID,
        "station": "kitchen",
        "status": KitchenTicketStatus.FIRED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return KitchenTicket(**defaults)


def _item(**overrides) -> KitchenItem:
    defaults = {
        "id": ITEM_ID,
        "tenant_id": TENANT_ID,
        "kitchen_ticket_id": TICKET_ID,
        "order_item_id": "order-item-1",
        "status": KitchenItemStatus.QUEUED,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return KitchenItem(**defaults)


class TestListKitchenTicketsUseCase:
    async def test_lists_tickets_for_the_branch_via_the_order_join(self) -> None:
        use_case = ListKitchenTicketsUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}, {}, {ORDER_ID: _order()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.tickets[0].id == TICKET_ID

    async def test_excludes_tickets_whose_order_belongs_to_a_different_branch(self) -> None:
        use_case = ListKitchenTicketsUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}, {}, {ORDER_ID: _order(branch_id="other-branch")}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 0


class TestUpdateKitchenTicketStatusUseCase:
    def _use_case(
        self, ticket_repo, order_repo, branch_repo, outbox
    ) -> UpdateKitchenTicketStatusUseCase:
        return UpdateKitchenTicketStatusUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: ticket_repo,
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"kitchen.manage"}))
            ),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_marks_ready_and_publishes_ticket_ready(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket(status=KitchenTicketStatus.IN_PROGRESS)}
            ),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
        )

        assert result.status == KitchenTicketStatus.READY.value
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], TicketReady)

    async def test_start_does_not_publish_ticket_ready(self) -> None:
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            InMemoryKitchenTicketRepository({TICKET_ID: _ticket()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="in_progress"),
        )

        assert result.status == KitchenTicketStatus.IN_PROGRESS.value
        assert len(outbox.published) == 0

    async def test_raises_not_found_for_an_unknown_ticket(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(),
            InMemoryOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            FakeOutboxWriter(),
        )

        with pytest.raises(KitchenTicketNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        use_case = UpdateKitchenTicketStatusUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}
            ),
            order_repository_factory=lambda _s: InMemoryOrderRepository({ORDER_ID: _order()}),
            branch_repository_factory=lambda _s: InMemoryBranchRepository({BRANCH_ID: _branch()}),
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions()
            ),
            outbox_writer_factory=lambda _s: FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenTicketStatusRequestDTO(kitchen_ticket_id=TICKET_ID, status="ready"),
            )


class TestUpdateKitchenItemStatusUseCase:
    def _use_case(self, ticket_repo, order_repo, branch_repo) -> UpdateKitchenItemStatusUseCase:
        return UpdateKitchenItemStatusUseCase(
            session_factory=_session_factory(),
            kitchen_ticket_repository_factory=lambda _s: ticket_repo,
            order_repository_factory=lambda _s: order_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(
                resolved=ResolvedPermissions(tenant_wide=frozenset({"kitchen.manage"}))
            ),
        )

    async def test_marks_an_item_ready_independently_of_its_ticket(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(
                {TICKET_ID: _ticket()}, {ITEM_ID: _item(status=KitchenItemStatus.IN_PROGRESS)}
            ),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ChangeKitchenItemStatusRequestDTO(kitchen_item_id=ITEM_ID, status="ready"),
        )

        assert result.status == KitchenItemStatus.READY.value

    async def test_raises_invalid_transition_for_an_out_of_order_status(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository({TICKET_ID: _ticket()}, {ITEM_ID: _item()}),
            InMemoryOrderRepository({ORDER_ID: _order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
        )

        with pytest.raises(InvalidKitchenItemStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenItemStatusRequestDTO(kitchen_item_id=ITEM_ID, status="ready"),
            )

    async def test_raises_not_found_for_an_unknown_item(self) -> None:
        use_case = self._use_case(
            InMemoryKitchenTicketRepository(),
            InMemoryOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
        )

        with pytest.raises(KitchenItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ChangeKitchenItemStatusRequestDTO(kitchen_item_id=ITEM_ID, status="ready"),
            )
