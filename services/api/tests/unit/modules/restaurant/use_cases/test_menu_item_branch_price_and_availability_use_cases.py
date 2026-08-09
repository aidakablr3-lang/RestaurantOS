"""Unit tests for MenuItemBranchPrice + MenuItemAvailability use cases
(Sprint 5 Step 4.10) -- in-memory fakes, no network/DB access.

``CreateXUseCase`` mirrors ``CreateQRCodeUseCase``'s own
resolve-and-authorize-branch security matrix (Step 4.6): tenant-wide
grant, matching branch-scoped grant, mismatched branch-scoped grant,
no grant, read-only grant. ``ListXUseCase`` mirrors
``ListAccessibleBranchesUseCase``'s tenant-wide-vs-branch-scoped
*filtering* shape instead (Step 4.0 Decision 2) -- a branch-scoped
reader is never denied outright, only shown a narrower slice, since
``list_for_menu_item`` has no branch filter of its own and could
otherwise leak another branch's pricing/availability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuItemAvailabilityRequestDTO,
    CreateMenuItemBranchPriceRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateMenuItemAvailabilityUseCase,
    CreateMenuItemBranchPriceUseCase,
    ListMenuItemAvailabilitiesUseCase,
    ListMenuItemBranchPricesUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    MenuItem,
    MenuItemAvailability,
    MenuItemBranchPrice,
)
from restaurant_os_api.modules.restaurant.domain.events import (
    MenuItemAvailabilityChanged,
    MenuItemBranchPriceChanged,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    EffectiveWindowOverlapError,
    MenuItemNotFoundError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryBranchRepository,
    InMemoryMenuItemAvailabilityRepository,
    InMemoryMenuItemBranchPriceRepository,
    InMemoryMenuItemRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
MENU_CATEGORY_ID = "01ARZ3NDEKTSV4RRFFQ6MCAT01"
MENU_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6MITM01"
FROM = datetime(2026, 1, 1, tzinfo=UTC)
TO = datetime(2026, 3, 1, tzinfo=UTC)


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
        "address_id": None,
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _menu_item(**overrides) -> MenuItem:
    defaults = {
        "id": MENU_ITEM_ID,
        "tenant_id": TENANT_ID,
        "menu_category_id": MENU_CATEGORY_ID,
        "name": "Margherita Pizza",
        "price_amount": Decimal("12.00"),
        "currency_code": "USD",
        "is_available": True,
        "display_order": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return MenuItem(**defaults)


def _branch_price_row(
    *, row_id: str, branch_id: str, effective_to: datetime | None = None
) -> MenuItemBranchPrice:
    return MenuItemBranchPrice(
        id=row_id,
        tenant_id=TENANT_ID,
        branch_id=branch_id,
        menu_item_id=MENU_ITEM_ID,
        price_amount=Decimal("9.99"),
        effective_from=FROM,
        effective_to=effective_to,
        created_at=datetime.now(UTC),
    )


def _availability_row(*, row_id: str, branch_id: str) -> MenuItemAvailability:
    return MenuItemAvailability(
        id=row_id,
        tenant_id=TENANT_ID,
        branch_id=branch_id,
        menu_item_id=MENU_ITEM_ID,
        is_available=False,
        effective_from=FROM,
        effective_to=None,
        created_at=datetime.now(UTC),
    )


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateMenuItemBranchPriceUseCase:
    def _use_case(
        self, menu_item_repo, branch_repo, price_repo, resolved, outbox
    ) -> CreateMenuItemBranchPriceUseCase:
        return CreateMenuItemBranchPriceUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
            branch_repository_factory=lambda _s: branch_repo,
            menu_item_branch_price_repository_factory=lambda _s: price_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_an_override_row_and_publishes_changed(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        outbox = FakeOutboxWriter()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo, branch_repo, InMemoryMenuItemBranchPriceRepository(), resolved, outbox
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateMenuItemBranchPriceRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                branch_id=BRANCH_ID,
                price_amount=Decimal("10.50"),
                effective_from=FROM,
                effective_to=TO,
            ),
        )

        assert result.menu_item_id == MENU_ITEM_ID
        assert result.branch_id == BRANCH_ID
        assert result.price_amount == Decimal("10.50")
        assert result.effective_to == TO
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], MenuItemBranchPriceChanged)

    async def test_effective_to_none_is_an_open_ended_window(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemBranchPriceRepository(),
            resolved,
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateMenuItemBranchPriceRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                branch_id=BRANCH_ID,
                price_amount=Decimal("10.50"),
                effective_from=FROM,
                effective_to=None,
            ),
        )

        assert result.effective_to is None

    async def test_a_non_overlapping_window_after_a_closed_one_succeeds(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        price_repo = InMemoryMenuItemBranchPriceRepository(
            {
                "row-1": _branch_price_row(row_id="row-1", branch_id=BRANCH_ID, effective_to=TO),
            }
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo, branch_repo, price_repo, resolved, FakeOutboxWriter()
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateMenuItemBranchPriceRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                branch_id=BRANCH_ID,
                price_amount=Decimal("10.50"),
                effective_from=TO,
                effective_to=None,
            ),
        )
        assert result.effective_from == TO

    async def test_an_overlapping_window_at_the_same_branch_raises_conflict(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        price_repo = InMemoryMenuItemBranchPriceRepository(
            {"row-1": _branch_price_row(row_id="row-1", branch_id=BRANCH_ID)}
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo, branch_repo, price_repo, resolved, FakeOutboxWriter()
        )

        with pytest.raises(EffectiveWindowOverlapError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemBranchPriceRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    price_amount=Decimal("10.50"),
                    effective_from=FROM,
                    effective_to=None,
                ),
            )

    async def test_an_overlapping_window_at_a_different_branch_does_not_conflict(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository(
            {BRANCH_ID: _branch(), OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        price_repo = InMemoryMenuItemBranchPriceRepository(
            {"row-1": _branch_price_row(row_id="row-1", branch_id=BRANCH_ID)}
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo, branch_repo, price_repo, resolved, FakeOutboxWriter()
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateMenuItemBranchPriceRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                branch_id=OTHER_BRANCH_ID,
                price_amount=Decimal("10.50"),
                effective_from=FROM,
                effective_to=None,
            ),
        )
        assert result.branch_id == OTHER_BRANCH_ID

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = self._use_case(
            InMemoryMenuItemRepository(),
            InMemoryBranchRepository(),
            InMemoryMenuItemBranchPriceRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"menu.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemBranchPriceRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    price_amount=Decimal("10.50"),
                    effective_from=FROM,
                ),
            )

    async def test_raises_not_found_for_a_cross_tenant_menu_item(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository(
            {MENU_ITEM_ID: _menu_item(tenant_id=OTHER_TENANT_ID)}
        )
        use_case = self._use_case(
            menu_item_repo,
            InMemoryBranchRepository(),
            InMemoryMenuItemBranchPriceRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"menu.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemBranchPriceRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    price_amount=Decimal("10.50"),
                    effective_from=FROM,
                ),
            )

    async def test_a_branch_scoped_manage_holder_can_set_a_price_at_their_own_branch(
        self,
    ) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"menu.manage"})})
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemBranchPriceRepository(),
            resolved,
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateMenuItemBranchPriceRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                branch_id=BRANCH_ID,
                price_amount=Decimal("10.50"),
                effective_from=FROM,
            ),
        )
        assert result.branch_id == BRANCH_ID

    async def test_a_branch_scoped_manage_holder_cannot_set_a_price_at_a_different_branch(
        self,
    ) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository(
            {OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"menu.manage"})})
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemBranchPriceRepository(),
            resolved,
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemBranchPriceRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=OTHER_BRANCH_ID,
                    price_amount=Decimal("10.50"),
                    effective_from=FROM,
                ),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemBranchPriceRepository(),
            ResolvedPermissions(),
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemBranchPriceRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    price_amount=Decimal("10.50"),
                    effective_from=FROM,
                ),
            )

    async def test_read_only_grant_is_insufficient(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.read"}))
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemBranchPriceRepository(),
            resolved,
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemBranchPriceRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    price_amount=Decimal("10.50"),
                    effective_from=FROM,
                ),
            )


class TestListMenuItemBranchPricesUseCase:
    def _use_case(self, menu_item_repo, price_repo, resolved) -> ListMenuItemBranchPricesUseCase:
        return ListMenuItemBranchPricesUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
            menu_item_branch_price_repository_factory=lambda _s: price_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_a_tenant_wide_reader_sees_every_branchs_rows(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        price_repo = InMemoryMenuItemBranchPriceRepository(
            {
                "row-1": _branch_price_row(row_id="row-1", branch_id=BRANCH_ID),
                "row-2": _branch_price_row(row_id="row-2", branch_id=OTHER_BRANCH_ID),
            }
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.read"}))
        use_case = self._use_case(menu_item_repo, price_repo, resolved)

        result = await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)

        assert {r.branch_id for r in result} == {BRANCH_ID, OTHER_BRANCH_ID}

    async def test_a_branch_scoped_reader_sees_only_their_own_branchs_rows(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        price_repo = InMemoryMenuItemBranchPriceRepository(
            {
                "row-1": _branch_price_row(row_id="row-1", branch_id=BRANCH_ID),
                "row-2": _branch_price_row(row_id="row-2", branch_id=OTHER_BRANCH_ID),
            }
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"menu.read"})})
        use_case = self._use_case(menu_item_repo, price_repo, resolved)

        result = await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)

        assert [r.branch_id for r in result] == [BRANCH_ID]

    async def test_no_grant_at_all_sees_nothing(self) -> None:
        # No route-level PermissionDeniedError here -- the coarse
        # require_permission_at_any_scope("menu.read") gate that would
        # reject this caller entirely lives in the router, not this use
        # case. Called directly (as here), a caller with no menu.read
        # grant anywhere simply has an empty accessible-branch set, so
        # the same tenant-wide-vs-branch-scoped filter that scopes a
        # branch-limited reader down to their own branch here scopes
        # this caller down to nothing.
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        price_repo = InMemoryMenuItemBranchPriceRepository(
            {"row-1": _branch_price_row(row_id="row-1", branch_id=BRANCH_ID)}
        )
        use_case = self._use_case(menu_item_repo, price_repo, ResolvedPermissions())

        result = await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)
        assert result == []

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = self._use_case(
            InMemoryMenuItemRepository(),
            InMemoryMenuItemBranchPriceRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"menu.read"})),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)


class TestCreateMenuItemAvailabilityUseCase:
    def _use_case(
        self, menu_item_repo, branch_repo, availability_repo, resolved, outbox
    ) -> CreateMenuItemAvailabilityUseCase:
        return CreateMenuItemAvailabilityUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
            branch_repository_factory=lambda _s: branch_repo,
            menu_item_availability_repository_factory=lambda _s: availability_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_creates_an_override_row_and_publishes_changed(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        outbox = FakeOutboxWriter()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemAvailabilityRepository(),
            resolved,
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CreateMenuItemAvailabilityRequestDTO(
                menu_item_id=MENU_ITEM_ID,
                branch_id=BRANCH_ID,
                is_available=False,
                effective_from=FROM,
                effective_to=TO,
            ),
        )

        assert result.is_available is False
        assert result.branch_id == BRANCH_ID
        assert len(outbox.published) == 1
        event = outbox.published[0][1]
        assert isinstance(event, MenuItemAvailabilityChanged)
        assert event.branch_id == BRANCH_ID

    async def test_an_overlapping_window_at_the_same_branch_raises_conflict(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        availability_repo = InMemoryMenuItemAvailabilityRepository(
            {"row-1": _availability_row(row_id="row-1", branch_id=BRANCH_ID)}
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.manage"}))
        use_case = self._use_case(
            menu_item_repo, branch_repo, availability_repo, resolved, FakeOutboxWriter()
        )

        with pytest.raises(EffectiveWindowOverlapError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemAvailabilityRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    is_available=False,
                    effective_from=FROM,
                    effective_to=None,
                ),
            )

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = self._use_case(
            InMemoryMenuItemRepository(),
            InMemoryBranchRepository(),
            InMemoryMenuItemAvailabilityRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"menu.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemAvailabilityRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    is_available=False,
                    effective_from=FROM,
                ),
            )

    async def test_a_branch_scoped_manage_holder_cannot_set_availability_at_a_different_branch(
        self,
    ) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository(
            {OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"menu.manage"})})
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemAvailabilityRepository(),
            resolved,
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemAvailabilityRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=OTHER_BRANCH_ID,
                    is_available=False,
                    effective_from=FROM,
                ),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            menu_item_repo,
            branch_repo,
            InMemoryMenuItemAvailabilityRepository(),
            ResolvedPermissions(),
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CreateMenuItemAvailabilityRequestDTO(
                    menu_item_id=MENU_ITEM_ID,
                    branch_id=BRANCH_ID,
                    is_available=False,
                    effective_from=FROM,
                ),
            )


class TestListMenuItemAvailabilitiesUseCase:
    def _use_case(
        self, menu_item_repo, availability_repo, resolved
    ) -> ListMenuItemAvailabilitiesUseCase:
        return ListMenuItemAvailabilitiesUseCase(
            session_factory=_session_factory(),
            menu_item_repository_factory=lambda _s: menu_item_repo,
            menu_item_availability_repository_factory=lambda _s: availability_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_a_branch_scoped_reader_sees_only_their_own_branchs_rows(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        availability_repo = InMemoryMenuItemAvailabilityRepository(
            {
                "row-1": _availability_row(row_id="row-1", branch_id=BRANCH_ID),
                "row-2": _availability_row(row_id="row-2", branch_id=OTHER_BRANCH_ID),
            }
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"menu.read"})})
        use_case = self._use_case(menu_item_repo, availability_repo, resolved)

        result = await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)

        assert [r.branch_id for r in result] == [BRANCH_ID]

    async def test_a_tenant_wide_reader_sees_every_branchs_rows(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        availability_repo = InMemoryMenuItemAvailabilityRepository(
            {
                "row-1": _availability_row(row_id="row-1", branch_id=BRANCH_ID),
                "row-2": _availability_row(row_id="row-2", branch_id=OTHER_BRANCH_ID),
            }
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"menu.read"}))
        use_case = self._use_case(menu_item_repo, availability_repo, resolved)

        result = await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)

        assert {r.branch_id for r in result} == {BRANCH_ID, OTHER_BRANCH_ID}

    async def test_no_grant_at_all_sees_nothing(self) -> None:
        menu_item_repo = InMemoryMenuItemRepository({MENU_ITEM_ID: _menu_item()})
        availability_repo = InMemoryMenuItemAvailabilityRepository(
            {"row-1": _availability_row(row_id="row-1", branch_id=BRANCH_ID)}
        )
        use_case = self._use_case(menu_item_repo, availability_repo, ResolvedPermissions())

        result = await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)
        assert result == []

    async def test_raises_not_found_for_an_unknown_menu_item(self) -> None:
        use_case = self._use_case(
            InMemoryMenuItemRepository(),
            InMemoryMenuItemAvailabilityRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"menu.read"})),
        )

        with pytest.raises(MenuItemNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", MENU_ITEM_ID)
