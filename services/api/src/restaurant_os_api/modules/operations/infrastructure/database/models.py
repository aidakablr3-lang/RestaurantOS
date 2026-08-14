"""SQLAlchemy ORM models for the operations module (Day-to-Day Operations).

Mirrors ``modules.restaurant.infrastructure.database.models``'s exact
conventions: every table composes ``ULIDPrimaryKeyMixin`` +
``TenantScopedMixin`` (+ ``BranchScopedMixin`` where applicable) +
``TimestampMixin`` (+ ``SoftDeleteMixin`` only where the entity's own
lifecycle is soft-deletable, never on an Immutable-lifecycle entity),
matching the migration's own column-for-column shape
(alembic/versions/0007_day_to_day_operations.py). No ``SyncVersionedMixin``
anywhere in this module -- the offline-sync Conflict Resolution Registry
is explicitly deferred (RestaurantOS_DayToDay_Operations_Architecture.md
SS8, "online-only v1").

Append-only/write-once tables (``BillAdjustmentModel``,
``OrderTaxLineModel``, ``LedgerEntryModel``, ``StockMovementModel``)
define ``created_at`` directly rather than composing ``TimestampMixin``,
matching ``MenuItemModifierGroupModel``'s own precedent for a
never-updated row.

``ChartOfAccountModel`` composes neither ``ULIDPrimaryKeyMixin`` nor
``TenantScopedMixin`` -- pure platform-seeded reference data with
``account_code`` as its own primary key, the same classification
``PermissionModel`` already has in the identity module.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import (
    Base,
    BranchScopedMixin,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    ULIDPrimaryKeyMixin,
)
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


def _created_at_column() -> Mapped[datetime]:
    return mapped_column(TimestampType(timezone=True), server_default=func.now(), nullable=False)


# --- Order Management --------------------------------------------------


class TabModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin):
    __tablename__ = "tabs"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('open', 'closed')", name="status_is_valid"),
    )

    table_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tables.id", ondelete="RESTRICT"), nullable=True
    )
    customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    opened_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)


class OrderModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "order_source IN ('pos', 'qr', 'delivery', 'takeaway')", name="order_source_is_valid"
        ),
        CheckConstraint(
            "status IN ('open', 'fired', 'served', 'billed', 'closed', 'voided')",
            name="status_is_valid",
        ),
        CheckConstraint("subtotal_amount >= 0", name="subtotal_amount_is_non_negative"),
        CheckConstraint("tax_amount >= 0", name="tax_amount_is_non_negative"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_is_iso4217"),
        Index("ix_orders_branch_id_status", "branch_id", "status"),
        Index("ix_orders_branch_id_opened_at", "branch_id", "opened_at"),
    )

    table_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tables.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    tab_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tabs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Customer doesn't exist yet (future CRM Platform) -- reserved,
    # unpopulated, no FK, matching ReservationModel.customer_id's pattern.
    customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    subtotal_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, server_default="0"
    )
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), Computed("subtotal_amount + tax_amount", persisted=True), nullable=False
    )
    currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)
    origin_device_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderItemModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "order_items"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("quantity > 0", name="quantity_is_positive"),
        CheckConstraint("unit_price_amount >= 0", name="unit_price_amount_is_non_negative"),
        CheckConstraint(
            "line_status IN ('added', 'fired', 'ready', 'served', 'voided')",
            name="line_status_is_valid",
        ),
    )

    order_id: Mapped[str] = mapped_column(
        Text, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    menu_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    modifiers_snapshot: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, server_default="[]"
    )
    recipe_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    line_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="added")


# --- Kitchen (KOT/KDS) --------------------------------------------------


class KitchenTicketModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "kitchen_tickets"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "status IN ('fired', 'in_progress', 'ready', 'served')", name="status_is_valid"
        ),
    )

    order_id: Mapped[str] = mapped_column(
        Text, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    station: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="fired")


class KitchenItemModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "kitchen_items"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('queued', 'in_progress', 'ready')", name="status_is_valid"),
    )

    kitchen_ticket_id: Mapped[str] = mapped_column(
        Text, ForeignKey("kitchen_tickets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")


# --- POS Billing ---------------------------------------------------------


class TaxModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "taxes"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("rate >= 0 AND rate <= 1", name="rate_is_valid"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class DiscountModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "discounts"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "discount_type IN ('percentage', 'fixed_amount')", name="discount_type_is_valid"
        ),
        CheckConstraint("value >= 0", name="value_is_non_negative"),
        CheckConstraint(
            "active_from < active_to OR active_to IS NULL", name="active_window_is_valid"
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    discount_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    active_from: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True
    )
    active_to: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)


class PromoCodeModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "promo_codes"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('active', 'exhausted', 'expired')", name="status_is_valid"),
        Index("uq_promo_codes_tenant_id_code", "tenant_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False)
    discount_id: Mapped[str] = mapped_column(
        Text, ForeignKey("discounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_customer_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")


class BillModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin):
    __tablename__ = "bills"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('open', 'partially_paid', 'closed')", name="status_is_valid"),
        # The XOR: a Bill closes out either exactly one Order or an
        # entire Tab, never both, never neither (Data Architecture v2.0
        # Group E).
        CheckConstraint(
            "(order_id IS NOT NULL AND tab_id IS NULL) OR (order_id IS NULL AND tab_id IS NOT NULL)",
            name="order_xor_tab",
        ),
    )

    order_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    tab_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tabs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")


class BillAdjustmentModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin):
    """Append-only -- applied once, never edited (Data Architecture v2.0
    Group B). No ``TimestampMixin``/``SoftDeleteMixin`` beyond
    ``created_at``, matching ``MenuItemModifierGroupModel``'s own
    classification for a never-updated row."""

    __tablename__ = "bill_adjustments"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "adjustment_type IN ('discount', 'service_charge', 'tip', 'comp', 'write_off')",
            name="adjustment_type_is_valid",
        ),
    )

    bill_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bills.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    adjustment_type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at_column()


class OrderTaxLineModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin):
    """Append-only -- written once at order-close (Data Architecture v2.0
    Group C)."""

    __tablename__ = "order_tax_lines"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("taxable_amount >= 0", name="taxable_amount_is_non_negative"),
        CheckConstraint("tax_amount >= 0", name="tax_amount_is_non_negative"),
    )

    order_id: Mapped[str] = mapped_column(
        Text, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tax_id: Mapped[str] = mapped_column(
        Text, ForeignKey("taxes.id", ondelete="RESTRICT"), nullable=False
    )
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    tax_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    created_at: Mapped[datetime] = _created_at_column()


# --- Payments ------------------------------------------------------------


class PaymentModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("tender_type IN ('cash', 'card', 'wallet')", name="tender_type_is_valid"),
        CheckConstraint("amount > 0", name="amount_is_positive"),
        CheckConstraint("tip_amount >= 0", name="tip_amount_is_non_negative"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_is_iso4217"),
        CheckConstraint(
            "status IN ('authorized', 'captured', 'settled', 'declined')", name="status_is_valid"
        ),
    )

    bill_id: Mapped[str] = mapped_column(
        Text, ForeignKey("bills.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tender_type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    tip_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    # PCI boundary: a passthrough reference only, never a raw card number.
    gateway_token_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_last4: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="authorized")


class RefundModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin):
    __tablename__ = "refunds"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("amount > 0", name="amount_is_positive"),
        CheckConstraint("status IN ('requested', 'approved', 'processed')", name="status_is_valid"),
    )

    payment_id: Mapped[str] = mapped_column(
        Text, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(
        Text, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Every refund needs a named approver -- the only mechanism for
    # correcting a closed Order/Bill/Payment.
    approved_by_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="requested")


class CashDrawerModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin
):
    __tablename__ = "cash_drawers"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('open', 'closed')", name="status_is_valid"),
        CheckConstraint("opening_float_amount >= 0", name="opening_float_amount_is_non_negative"),
    )

    # Passthrough provenance only, no Terminal/Device entity yet.
    terminal_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    opening_float_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    closing_counted_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)


# --- Financial Ledger ----------------------------------------------------


class ChartOfAccountModel(Base, TimestampMixin):
    """No ``ULIDPrimaryKeyMixin``/``TenantScopedMixin`` -- pure
    platform-seeded reference data with ``account_code`` as its own
    primary key, the same classification ``PermissionModel`` already
    has in the identity module."""

    __tablename__ = "chart_of_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('asset', 'liability', 'revenue', 'expense', 'equity')",
            name="account_type_is_valid",
        ),
    )

    account_code: Mapped[str] = mapped_column(Text, primary_key=True)
    account_name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)


class LedgerEntryModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin):
    """Append-only -- written once, in the same transaction as the fact
    it records (Data Architecture v2.0 Group I)."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("entry_type IN ('debit', 'credit')", name="entry_type_is_valid"),
        CheckConstraint("amount > 0", name="amount_is_positive"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_is_iso4217"),
        Index("ix_ledger_entries_reference_type_reference_id", "reference_type", "reference_id"),
    )

    entry_type: Mapped[str] = mapped_column(Text, nullable=False)
    account_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("chart_of_accounts.account_code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created_at_column()


# --- Inventory & Recipes (food only) --------------------------------------


class RecipeModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "recipes"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("version > 0", name="version_is_positive"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # Editing a recipe creates a new row and repoints menu_items.recipe_id
    # rather than editing history in place.
    superseded_by_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=True
    )


class RecipeIngredientModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("quantity > 0", name="quantity_is_positive"),
    )

    recipe_id: Mapped[str] = mapped_column(
        Text, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inventory_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)


class InventoryCategoryModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "inventory_categories"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index("uq_inventory_categories_tenant_id_name", "tenant_id", "name", unique=True),
        CheckConstraint("category_type IN ('food', 'beverage')", name="category_type_is_valid"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    category_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="food")


class InventoryItemModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "inventory_items"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "reorder_point IS NULL OR reorder_point >= 0", name="reorder_point_is_non_negative"
        ),
        Index("uq_inventory_items_branch_id_name", "branch_id", "name", unique=True),
    )

    inventory_category_id: Mapped[str] = mapped_column(
        Text, ForeignKey("inventory_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    # Derived/cached -- maintained exclusively by the
    # enforce_stock_movement_and_update_balance() database trigger,
    # never hand-written by application code.
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, server_default="0"
    )
    reorder_point: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    allow_negative_stock_override: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class StockMovementModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin):
    """Append-only -- written once, never edited (Data Architecture v2.0
    Group D). No ``TimestampMixin``/``SoftDeleteMixin`` beyond
    ``created_at``."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "movement_type IN ('sale_deduction', 'adjustment', 'receipt', 'waste', 'transfer')",
            name="movement_type_is_valid",
        ),
        CheckConstraint("quantity_delta <> 0", name="quantity_delta_is_nonzero"),
        Index(
            "ix_stock_movements_inventory_item_id_occurred_at", "inventory_item_id", "occurred_at"
        ),
    )

    inventory_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False
    )
    movement_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created_at_column()


class StockAdjustmentModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin
):
    __tablename__ = "stock_adjustments"
    __table_args__ = (ulid_check_constraint("id"),)

    inventory_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stock_movement_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("stock_movements.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


# --- Purchasing ------------------------------------------------------------


class SupplierModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    """Tenant-level, NOT branch-scoped -- a supplier typically serves
    every branch of a tenant."""

    __tablename__ = "suppliers"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('active', 'inactive')", name="status_is_valid"),
        Index("uq_suppliers_tenant_id_name", "tenant_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    address_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")


class PurchaseOrderModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin
):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "status IN ('draft', 'sent', 'partially_received', 'fully_received', 'canceled')",
            name="status_is_valid",
        ),
    )

    supplier_id: Mapped[str] = mapped_column(
        Text, ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")


class PurchaseOrderItemModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("quantity_ordered > 0", name="quantity_ordered_is_positive"),
        CheckConstraint("quantity_received >= 0", name="quantity_received_is_non_negative"),
    )

    purchase_order_id: Mapped[str] = mapped_column(
        Text, ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inventory_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, server_default="0"
    )


class GoodsReceiptModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "goods_receipts"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('created', 'confirmed')", name="status_is_valid"),
    )

    purchase_order_id: Mapped[str] = mapped_column(
        Text, ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="created")
    received_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    has_discrepancy: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


__all__ = [
    "BillAdjustmentModel",
    "BillModel",
    "CashDrawerModel",
    "ChartOfAccountModel",
    "DiscountModel",
    "GoodsReceiptModel",
    "InventoryCategoryModel",
    "InventoryItemModel",
    "KitchenItemModel",
    "KitchenTicketModel",
    "LedgerEntryModel",
    "OrderItemModel",
    "OrderModel",
    "OrderTaxLineModel",
    "PaymentModel",
    "PromoCodeModel",
    "PurchaseOrderItemModel",
    "PurchaseOrderModel",
    "RecipeIngredientModel",
    "RecipeModel",
    "RefundModel",
    "StockAdjustmentModel",
    "StockMovementModel",
    "SupplierModel",
    "TabModel",
    "TaxModel",
]
