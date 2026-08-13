"""Unit tests for Supplier use cases (Sprint 7 Step 6) -- in-memory
fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.operations.application.dto import (
    CreateSupplierRequestDTO,
    UpdateSupplierRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    CreateSupplierUseCase,
    ListSuppliersUseCase,
    UpdateSupplierUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import Supplier, SupplierStatus
from restaurant_os_api.modules.operations.domain.exceptions import (
    SupplierNameConflictError,
    SupplierNotFoundError,
)
from restaurant_os_api.modules.restaurant.application.dto import AddressRequestDTO
from restaurant_os_api.modules.restaurant.domain.entities import Address
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    InMemorySupplierRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryAddressRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
SUPPLIER_ID = "01ARZ3NDEKTSV4RRFFQ6SUP001"
ADDRESS_ID = "01ARZ3NDEKTSV4RRFFQ6ADR001"


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _supplier(**overrides) -> Supplier:
    defaults = {
        "id": SUPPLIER_ID,
        "tenant_id": TENANT_ID,
        "name": "Fresh Foods Co",
        "status": SupplierStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Supplier(**defaults)


def _address(**overrides) -> Address:
    defaults = {
        "id": ADDRESS_ID,
        "tenant_id": TENANT_ID,
        "created_at": datetime.now(UTC),
        "line1": "1 Market St",
        "city": "Springfield",
        "country_code": "US",
        "postal_code": "00000",
    }
    defaults.update(overrides)
    return Address(**defaults)


class TestCreateSupplierUseCase:
    def _use_case(self, supplier_repo, address_repo) -> CreateSupplierUseCase:
        return CreateSupplierUseCase(
            session_factory=_session_factory(),
            supplier_repository_factory=lambda _s: supplier_repo,
            address_repository_factory=lambda _s: address_repo,
        )

    async def test_creates_a_supplier_without_an_address(self) -> None:
        use_case = self._use_case(InMemorySupplierRepository(), InMemoryAddressRepository())

        result = await use_case.execute(TENANT_ID, CreateSupplierRequestDTO(name="Fresh Foods Co"))

        assert result.name == "Fresh Foods Co"
        assert result.status == "active"
        assert result.address is None

    async def test_creates_a_supplier_with_an_address(self) -> None:
        use_case = self._use_case(InMemorySupplierRepository(), InMemoryAddressRepository())

        result = await use_case.execute(
            TENANT_ID,
            CreateSupplierRequestDTO(
                name="Fresh Foods Co",
                address=AddressRequestDTO(
                    line1="1 Market St", city="Springfield", country_code="US", postal_code="00000"
                ),
            ),
        )

        assert result.address is not None
        assert result.address.line1 == "1 Market St"

    async def test_raises_name_conflict_for_a_duplicate_name(self) -> None:
        use_case = self._use_case(
            InMemorySupplierRepository({SUPPLIER_ID: _supplier()}), InMemoryAddressRepository()
        )

        with pytest.raises(SupplierNameConflictError):
            await use_case.execute(TENANT_ID, CreateSupplierRequestDTO(name="Fresh Foods Co"))


class TestUpdateSupplierUseCase:
    def _use_case(self, supplier_repo, address_repo) -> UpdateSupplierUseCase:
        return UpdateSupplierUseCase(
            session_factory=_session_factory(),
            supplier_repository_factory=lambda _s: supplier_repo,
            address_repository_factory=lambda _s: address_repo,
        )

    async def test_updates_name_and_status(self) -> None:
        use_case = self._use_case(
            InMemorySupplierRepository({SUPPLIER_ID: _supplier()}), InMemoryAddressRepository()
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateSupplierRequestDTO(
                supplier_id=SUPPLIER_ID, name="Fresher Foods Co", status="inactive"
            ),
        )

        assert result.name == "Fresher Foods Co"
        assert result.status == "inactive"

    async def test_adds_a_new_address_when_the_supplier_previously_had_none(self) -> None:
        use_case = self._use_case(
            InMemorySupplierRepository({SUPPLIER_ID: _supplier()}), InMemoryAddressRepository()
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateSupplierRequestDTO(
                supplier_id=SUPPLIER_ID,
                name="Fresh Foods Co",
                status="active",
                address=AddressRequestDTO(
                    line1="2 Market St", city="Springfield", country_code="US", postal_code="00001"
                ),
            ),
        )

        assert result.address is not None
        assert result.address.line1 == "2 Market St"

    async def test_updates_the_existing_address_in_place(self) -> None:
        use_case = self._use_case(
            InMemorySupplierRepository({SUPPLIER_ID: _supplier(address_id=ADDRESS_ID)}),
            InMemoryAddressRepository({ADDRESS_ID: _address()}),
        )

        result = await use_case.execute(
            TENANT_ID,
            UpdateSupplierRequestDTO(
                supplier_id=SUPPLIER_ID,
                name="Fresh Foods Co",
                status="active",
                address=AddressRequestDTO(
                    line1="Updated St", city="Springfield", country_code="US", postal_code="00000"
                ),
            ),
        )

        assert result.address is not None
        assert result.address.line1 == "Updated St"

    async def test_raises_name_conflict_when_renamed_to_an_existing_suppliers_name(self) -> None:
        other = _supplier(id="other-supplier", name="Other Foods")
        use_case = self._use_case(
            InMemorySupplierRepository({SUPPLIER_ID: _supplier(), "other-supplier": other}),
            InMemoryAddressRepository(),
        )

        with pytest.raises(SupplierNameConflictError):
            await use_case.execute(
                TENANT_ID,
                UpdateSupplierRequestDTO(
                    supplier_id=SUPPLIER_ID, name="Other Foods", status="active"
                ),
            )

    async def test_raises_not_found_for_an_unknown_supplier(self) -> None:
        use_case = self._use_case(InMemorySupplierRepository(), InMemoryAddressRepository())

        with pytest.raises(SupplierNotFoundError):
            await use_case.execute(
                TENANT_ID,
                UpdateSupplierRequestDTO(
                    supplier_id=SUPPLIER_ID, name="Fresh Foods Co", status="active"
                ),
            )


class TestListSuppliersUseCase:
    async def test_lists_suppliers_resolving_their_addresses(self) -> None:
        use_case = ListSuppliersUseCase(
            session_factory=_session_factory(),
            supplier_repository_factory=lambda _s: InMemorySupplierRepository(
                {SUPPLIER_ID: _supplier(address_id=ADDRESS_ID)}
            ),
            address_repository_factory=lambda _s: InMemoryAddressRepository(
                {ADDRESS_ID: _address()}
            ),
        )

        result = await use_case.execute(TENANT_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.suppliers[0].address is not None
        assert result.suppliers[0].address.line1 == "1 Market St"
