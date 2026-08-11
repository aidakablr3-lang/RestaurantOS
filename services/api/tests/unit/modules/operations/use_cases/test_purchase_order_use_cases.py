"""Unit tests for PurchaseOrder/GoodsReceipt use cases (Sprint 7 Step 6)
-- in-memory fakes, no network/DB access."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.operations.application.dto import (
    AddPurchaseOrderItemRequestDTO,
    ConfirmGoodsReceiptLineRequestDTO,
    ConfirmGoodsReceiptRequestDTO,
    CreatePurchaseOrderRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases import (
    AddPurchaseOrderItemUseCase,
    CancelPurchaseOrderUseCase,
    ConfirmGoodsReceiptUseCase,
    CreatePurchaseOrderUseCase,
    GetPurchaseOrderUseCase,
    ListPurchaseOrdersUseCase,
    SendPurchaseOrderUseCase,
)
from restaurant_os_api.modules.operations.domain.entities import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Supplier,
    SupplierStatus,
)
from restaurant_os_api.modules.operations.domain.exceptions import (
    InvalidPurchaseOrderStatusTransitionError,
    InventoryItemNotFoundError,
    PurchaseOrderHasNoItemsError,
    PurchaseOrderItemNotFoundError,
    PurchaseOrderNotFoundError,
    SupplierNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.entities import Branch, BranchStatus
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from tests.unit.modules.operations.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryGoodsReceiptRepository,
    InMemoryInventoryItemRepository,
    InMemoryPurchaseOrderRepository,
    InMemoryStockMovementRepository,
    InMemorySupplierRepository,
    fake_session_factory_returning,
)
from tests.unit.modules.restaurant.fakes import InMemoryBranchRepository

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
SUPPLIER_ID = "01ARZ3NDEKTSV4RRFFQ6SUP001"
PO_ID = "01ARZ3NDEKTSV4RRFFQ6PO0001"
PO_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6POI001"
INVENTORY_ITEM_ID = "01ARZ3NDEKTSV4RRFFQ6IITM01"


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


def _purchase_order(**overrides) -> PurchaseOrder:
    defaults = {
        "id": PO_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "supplier_id": SUPPLIER_ID,
        "status": PurchaseOrderStatus.DRAFT,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return PurchaseOrder(**defaults)


def _po_item(**overrides) -> PurchaseOrderItem:
    defaults = {
        "id": PO_ITEM_ID,
        "tenant_id": TENANT_ID,
        "purchase_order_id": PO_ID,
        "inventory_item_id": INVENTORY_ITEM_ID,
        "quantity_ordered": Decimal(10),
        "quantity_received": Decimal(0),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return PurchaseOrderItem(**defaults)


def _inventory_item(**overrides) -> InventoryItem:
    defaults = {
        "id": INVENTORY_ITEM_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "inventory_category_id": "category-1",
        "name": "Beef Patty",
        "unit": "each",
        "quantity_on_hand": Decimal(0),
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return InventoryItem(**defaults)


class TestCreatePurchaseOrderUseCase:
    def _use_case(self, branch_repo, supplier_repo, po_repo) -> CreatePurchaseOrderUseCase:
        return CreatePurchaseOrderUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: po_repo,
            supplier_repository_factory=lambda _s: supplier_repo,
            branch_repository_factory=lambda _s: branch_repo,
        )

    async def test_creates_a_draft_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemorySupplierRepository({SUPPLIER_ID: _supplier()}),
            InMemoryPurchaseOrderRepository(),
        )

        result = await use_case.execute(
            TENANT_ID, CreatePurchaseOrderRequestDTO(branch_id=BRANCH_ID, supplier_id=SUPPLIER_ID)
        )

        assert result.status == "draft"
        assert result.items == []

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository(),
            InMemorySupplierRepository({SUPPLIER_ID: _supplier()}),
            InMemoryPurchaseOrderRepository(),
        )

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreatePurchaseOrderRequestDTO(branch_id=BRANCH_ID, supplier_id=SUPPLIER_ID),
            )

    async def test_raises_not_found_for_an_unknown_supplier(self) -> None:
        use_case = self._use_case(
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            InMemorySupplierRepository(),
            InMemoryPurchaseOrderRepository(),
        )

        with pytest.raises(SupplierNotFoundError):
            await use_case.execute(
                TENANT_ID,
                CreatePurchaseOrderRequestDTO(branch_id=BRANCH_ID, supplier_id=SUPPLIER_ID),
            )


class TestAddPurchaseOrderItemUseCase:
    def _use_case(self, po_repo, item_repo, branch_repo, resolved) -> AddPurchaseOrderItemUseCase:
        return AddPurchaseOrderItemUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: po_repo,
            inventory_item_repository_factory=lambda _s: item_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_adds_an_item_to_a_draft_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}),
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            AddPurchaseOrderItemRequestDTO(
                purchase_order_id=PO_ID,
                inventory_item_id=INVENTORY_ITEM_ID,
                quantity_ordered=Decimal(10),
            ),
        )

        assert len(result.items) == 1
        assert result.items[0].quantity_ordered == Decimal(10)

    async def test_raises_invalid_transition_for_a_non_draft_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(
                {PO_ID: _purchase_order(status=PurchaseOrderStatus.SENT)}
            ),
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(InvalidPurchaseOrderStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddPurchaseOrderItemRequestDTO(
                    purchase_order_id=PO_ID,
                    inventory_item_id=INVENTORY_ITEM_ID,
                    quantity_ordered=Decimal(10),
                ),
            )

    async def test_raises_not_found_for_an_unknown_inventory_item(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}),
            InMemoryInventoryItemRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(InventoryItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddPurchaseOrderItemRequestDTO(
                    purchase_order_id=PO_ID,
                    inventory_item_id=INVENTORY_ITEM_ID,
                    quantity_ordered=Decimal(10),
                ),
            )

    async def test_raises_not_found_for_an_unknown_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(),
            InMemoryInventoryItemRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(PurchaseOrderNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddPurchaseOrderItemRequestDTO(
                    purchase_order_id=PO_ID,
                    inventory_item_id=INVENTORY_ITEM_ID,
                    quantity_ordered=Decimal(10),
                ),
            )

    async def test_no_grant_at_all_is_denied(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}),
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                AddPurchaseOrderItemRequestDTO(
                    purchase_order_id=PO_ID,
                    inventory_item_id=INVENTORY_ITEM_ID,
                    quantity_ordered=Decimal(10),
                ),
            )


class TestSendPurchaseOrderUseCase:
    def _use_case(self, po_repo, branch_repo, resolved) -> SendPurchaseOrderUseCase:
        return SendPurchaseOrderUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: po_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_sends_a_draft_purchase_order_with_items(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}, {PO_ITEM_ID: _po_item()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", PO_ID)

        assert result.status == "sent"

    async def test_raises_has_no_items_for_an_empty_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(PurchaseOrderHasNoItemsError):
            await use_case.execute(TENANT_ID, "user-1", PO_ID)

    async def test_raises_not_found_for_an_unknown_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(PurchaseOrderNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", PO_ID)


class TestCancelPurchaseOrderUseCase:
    def _use_case(self, po_repo, branch_repo, resolved) -> CancelPurchaseOrderUseCase:
        return CancelPurchaseOrderUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: po_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_cancels_a_draft_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        result = await use_case.execute(TENANT_ID, "user-1", PO_ID)

        assert result.status == "canceled"

    async def test_raises_invalid_transition_for_a_fully_received_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(
                {PO_ID: _purchase_order(status=PurchaseOrderStatus.FULLY_RECEIVED)}
            ),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(InvalidPurchaseOrderStatusTransitionError):
            await use_case.execute(TENANT_ID, "user-1", PO_ID)

    async def test_raises_not_found_for_an_unknown_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
        )

        with pytest.raises(PurchaseOrderNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", PO_ID)


class TestGetPurchaseOrderUseCase:
    async def test_returns_the_purchase_order_with_its_items(self) -> None:
        use_case = GetPurchaseOrderUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: InMemoryPurchaseOrderRepository(
                {PO_ID: _purchase_order()}, {PO_ITEM_ID: _po_item()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, PO_ID)

        assert len(result.items) == 1

    async def test_raises_not_found_for_a_purchase_order_at_a_different_branch(self) -> None:
        use_case = GetPurchaseOrderUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: InMemoryPurchaseOrderRepository(
                {PO_ID: _purchase_order(branch_id=OTHER_BRANCH_ID)}
            ),
        )

        with pytest.raises(PurchaseOrderNotFoundError):
            await use_case.execute(TENANT_ID, BRANCH_ID, PO_ID)


class TestListPurchaseOrdersUseCase:
    async def test_lists_purchase_orders_for_the_branch_without_items(self) -> None:
        use_case = ListPurchaseOrdersUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: InMemoryPurchaseOrderRepository(
                {PO_ID: _purchase_order()}, {PO_ITEM_ID: _po_item()}
            ),
        )

        result = await use_case.execute(TENANT_ID, BRANCH_ID, offset=0, limit=20)

        assert result.total == 1
        assert result.purchase_orders[0].items == []


class TestConfirmGoodsReceiptUseCase:
    def _use_case(
        self, po_repo, receipt_repo, item_repo, movement_repo, branch_repo, resolved, outbox
    ) -> ConfirmGoodsReceiptUseCase:
        return ConfirmGoodsReceiptUseCase(
            session_factory=_session_factory(),
            purchase_order_repository_factory=lambda _s: po_repo,
            goods_receipt_repository_factory=lambda _s: receipt_repo,
            inventory_item_repository_factory=lambda _s: item_repo,
            stock_movement_repository_factory=lambda _s: movement_repo,
            branch_repository_factory=lambda _s: branch_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_full_receipt_marks_the_po_fully_received_and_updates_stock(self) -> None:
        items = {INVENTORY_ITEM_ID: _inventory_item(quantity_on_hand=Decimal(0))}
        item_repo = InMemoryInventoryItemRepository(items)
        movement_repo = InMemoryStockMovementRepository(inventory_items=items)
        po_repo = InMemoryPurchaseOrderRepository(
            {PO_ID: _purchase_order(status=PurchaseOrderStatus.SENT)}, {PO_ITEM_ID: _po_item()}
        )
        outbox = FakeOutboxWriter()
        use_case = self._use_case(
            po_repo,
            InMemoryGoodsReceiptRepository(),
            item_repo,
            movement_repo,
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
            outbox,
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ConfirmGoodsReceiptRequestDTO(
                purchase_order_id=PO_ID,
                lines=[
                    ConfirmGoodsReceiptLineRequestDTO(
                        purchase_order_item_id=PO_ITEM_ID, quantity_received=Decimal(10)
                    )
                ],
            ),
        )

        assert result.status == "confirmed"
        assert result.has_discrepancy is False
        assert result.purchase_order.status == "fully_received"
        updated_item = await item_repo.get_by_id(TENANT_ID, INVENTORY_ITEM_ID)
        assert updated_item is not None
        assert updated_item.quantity_on_hand == Decimal(10)
        assert len(outbox.published) == 1

    async def test_partial_receipt_marks_the_po_partially_received(self) -> None:
        items = {INVENTORY_ITEM_ID: _inventory_item()}
        po_repo = InMemoryPurchaseOrderRepository(
            {PO_ID: _purchase_order(status=PurchaseOrderStatus.SENT)}, {PO_ITEM_ID: _po_item()}
        )
        use_case = self._use_case(
            po_repo,
            InMemoryGoodsReceiptRepository(),
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ConfirmGoodsReceiptRequestDTO(
                purchase_order_id=PO_ID,
                lines=[
                    ConfirmGoodsReceiptLineRequestDTO(
                        purchase_order_item_id=PO_ITEM_ID, quantity_received=Decimal(4)
                    )
                ],
            ),
        )

        assert result.purchase_order.status == "partially_received"

    async def test_over_receipt_is_flagged_as_a_discrepancy(self) -> None:
        items = {INVENTORY_ITEM_ID: _inventory_item()}
        po_repo = InMemoryPurchaseOrderRepository(
            {PO_ID: _purchase_order(status=PurchaseOrderStatus.SENT)}, {PO_ITEM_ID: _po_item()}
        )
        use_case = self._use_case(
            po_repo,
            InMemoryGoodsReceiptRepository(),
            InMemoryInventoryItemRepository(items),
            InMemoryStockMovementRepository(inventory_items=items),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
            FakeOutboxWriter(),
        )

        result = await use_case.execute(
            TENANT_ID,
            "user-1",
            ConfirmGoodsReceiptRequestDTO(
                purchase_order_id=PO_ID,
                lines=[
                    ConfirmGoodsReceiptLineRequestDTO(
                        purchase_order_item_id=PO_ITEM_ID, quantity_received=Decimal(15)
                    )
                ],
            ),
        )

        assert result.has_discrepancy is True

    async def test_raises_invalid_transition_for_a_draft_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository({PO_ID: _purchase_order()}, {PO_ITEM_ID: _po_item()}),
            InMemoryGoodsReceiptRepository(),
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            InMemoryStockMovementRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(InvalidPurchaseOrderStatusTransitionError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ConfirmGoodsReceiptRequestDTO(
                    purchase_order_id=PO_ID,
                    lines=[
                        ConfirmGoodsReceiptLineRequestDTO(
                            purchase_order_item_id=PO_ITEM_ID, quantity_received=Decimal(1)
                        )
                    ],
                ),
            )

    async def test_raises_not_found_for_an_unknown_purchase_order_item(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(
                {PO_ID: _purchase_order(status=PurchaseOrderStatus.SENT)}
            ),
            InMemoryGoodsReceiptRepository(),
            InMemoryInventoryItemRepository({INVENTORY_ITEM_ID: _inventory_item()}),
            InMemoryStockMovementRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(PurchaseOrderItemNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ConfirmGoodsReceiptRequestDTO(
                    purchase_order_id=PO_ID,
                    lines=[
                        ConfirmGoodsReceiptLineRequestDTO(
                            purchase_order_item_id=PO_ITEM_ID, quantity_received=Decimal(1)
                        )
                    ],
                ),
            )

    async def test_raises_not_found_for_an_unknown_purchase_order(self) -> None:
        use_case = self._use_case(
            InMemoryPurchaseOrderRepository(),
            InMemoryGoodsReceiptRepository(),
            InMemoryInventoryItemRepository(),
            InMemoryStockMovementRepository(),
            InMemoryBranchRepository({BRANCH_ID: _branch()}),
            ResolvedPermissions(tenant_wide=frozenset({"purchasing.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(PurchaseOrderNotFoundError):
            await use_case.execute(
                TENANT_ID,
                "user-1",
                ConfirmGoodsReceiptRequestDTO(purchase_order_id=PO_ID, lines=[]),
            )
