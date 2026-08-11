"""Unit tests for Discount use cases (Sprint 7 Step 4) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from restaurant_os_api.modules.operations.application.dto import CreateDiscountRequestDTO
from restaurant_os_api.modules.operations.application.use_cases import (
    CreateDiscountUseCase,
    ListDiscountsUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import Discount, DiscountType
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    InMemoryDiscountRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
DISCOUNT_ID = "01ARZ3NDEKTSV4RRFFQ6DISC01"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _discount(**overrides) -> Discount:
    defaults = {
        "id": DISCOUNT_ID,
        "tenant_id": TENANT_ID,
        "name": "Staff meal",
        "discount_type": DiscountType.PERCENTAGE,
        "value": Decimal(50),
        "requires_approval": False,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Discount(**defaults)


class TestCreateDiscountUseCase:
    async def test_creates_a_percentage_discount(self) -> None:
        use_case = CreateDiscountUseCase(
            session_factory=_session_factory(),
            discount_repository_factory=lambda _s: InMemoryDiscountRepository(),
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateDiscountRequestDTO(
                name="Happy hour", discount_type="percentage", value=Decimal(20)
            ),
        )

        assert result.name == "Happy hour"
        assert result.discount_type == "percentage"
        assert result.value == Decimal(20)
        assert result.requires_approval is False

    async def test_creates_a_discount_requiring_approval(self) -> None:
        use_case = CreateDiscountUseCase(
            session_factory=_session_factory(),
            discount_repository_factory=lambda _s: InMemoryDiscountRepository(),
        )

        result = await use_case.execute(
            TENANT_ID,
            CreateDiscountRequestDTO(
                name="Manager comp",
                discount_type="fixed_amount",
                value=Decimal(10),
                requires_approval=True,
            ),
        )

        assert result.requires_approval is True


class TestListDiscountsUseCase:
    async def test_lists_discounts_for_the_tenant_with_pagination(self) -> None:
        use_case = ListDiscountsUseCase(
            session_factory=_session_factory(),
            discount_repository_factory=lambda _s: InMemoryDiscountRepository(
                {DISCOUNT_ID: _discount()}
            ),
        )

        result = await use_case.execute(TENANT_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.discounts[0].id == DISCOUNT_ID

    async def test_excludes_discounts_belonging_to_a_different_tenant(self) -> None:
        use_case = ListDiscountsUseCase(
            session_factory=_session_factory(),
            discount_repository_factory=lambda _s: InMemoryDiscountRepository(
                {DISCOUNT_ID: _discount(tenant_id="other-tenant")}
            ),
        )

        result = await use_case.execute(TENANT_ID, offset=0, limit=20)

        assert result.total == 0
