"""Unit tests for CashDrawer use cases (Sprint 7 Step 4) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    CloseCashDrawerRequestDTO,
    OpenCashDrawerRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    CloseCashDrawerUseCase,
    OpenCashDrawerUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import CashDrawer, CashDrawerStatus
from restaurant_os_api.modules.operations.domain.exceptions import (
    CashDrawerAlreadyOpenError,
    CashDrawerNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import Branch, BranchStatus
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeResolveUserPermissionsUseCase,
    InMemoryCashDrawerRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
DRAWER_ID = "01ARZ3NDEKTSV4RRFFQ6DRWR01"


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


def _drawer(**overrides) -> CashDrawer:
    defaults = {
        "id": DRAWER_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "status": CashDrawerStatus.OPEN,
        "opening_float_amount": Decimal(100),
        "opened_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return CashDrawer(**defaults)


class TestOpenCashDrawerUseCase:
    def _use_case(self, branch_repo, drawer_repo) -> OpenCashDrawerUseCase:
        return OpenCashDrawerUseCase(
            session_factory=_session_factory(),
            cash_drawer_repository_factory=lambda _s: drawer_repo,
            branch_repository_factory=lambda _s: branch_repo,
        )

    async def test_opens_a_drawer_for_the_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}), InMemoryCashDrawerRepository()
        )

        result = await use_case.execute(
            TENANT_ID,
            OpenCashDrawerRequestDTO(branch_id=BRANCH_ID, opening_float_amount=Decimal(100)),
        )

        assert result.status == "open"
        assert result.opening_float_amount == Decimal(100)

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(InMemoryBranchRepository(), InMemoryCashDrawerRepository())

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID,
                OpenCashDrawerRequestDTO(branch_id=BRANCH_ID, opening_float_amount=Decimal(100)),
            )

    async def test_raises_already_open_when_the_branch_already_has_an_open_drawer(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemoryCashDrawerRepository({DRAWER_ID: _drawer()}),
        )

        with pytest.raises(CashDrawerAlreadyOpenError):
            await use_case.execute(
                TENANT_ID,
                OpenCashDrawerRequestDTO(branch_id=BRANCH_ID, opening_float_amount=Decimal(50)),
            )


class TestCloseCashDrawerUseCase:
    def _use_case(self, drawer_repo, branch_repo, resolved) -> CloseCashDrawerUseCase:
        return CloseCashDrawerUseCase(
            session_factory=_session_factory(),
            cash_drawer_repository_factory=lambda _s: drawer_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_closes_the_drawer_and_computes_expected_cash_and_variance(self) -> None:
        use_case = self._use_case(
            InMemoryCashDrawerRepository({DRAWER_ID: _drawer()}, settled_cash_total=Decimal(200)),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            CloseCashDrawerRequestDTO(
                cash_drawer_id=DRAWER_ID, closing_counted_amount=Decimal(290)
            ),
        )

        assert result.status == "closed"
        assert result.expected_cash_amount == Decimal(300)
        assert result.variance_amount == Decimal(-10)

    async def test_raises_not_found_for_an_unknown_drawer(self) -> None:
        use_case = self._use_case(
            InMemoryCashDrawerRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"billing.manage"})),
        )

        with pytest.raises(CashDrawerNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CloseCashDrawerRequestDTO(
                    cash_drawer_id=DRAWER_ID, closing_counted_amount=Decimal(100)
                ),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        use_case = self._use_case(
            InMemoryCashDrawerRepository({DRAWER_ID: _drawer()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                CloseCashDrawerRequestDTO(
                    cash_drawer_id=DRAWER_ID, closing_counted_amount=Decimal(100)
                ),
            )
