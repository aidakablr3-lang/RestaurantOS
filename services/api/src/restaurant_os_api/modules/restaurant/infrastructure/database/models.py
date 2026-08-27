"""SQLAlchemy ORM models for the restaurant module.

Mirrors ``modules.identity.infrastructure.database.models``'s exact
conventions: every table composes ``ULIDPrimaryKeyMixin`` +
``TenantScopedMixin`` (+ ``BranchScopedMixin`` where applicable) +
``TimestampMixin`` + ``SoftDeleteMixin``, matching the migration's own
column-for-column shape (alembic/versions/0004_restaurant_platform.py).
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import (
    Base,
    BranchScopedMixin,
    SoftDeleteMixin,
    SyncVersionedMixin,
    TenantScopedMixin,
    TimestampMixin,
    ULIDPrimaryKeyMixin,
)
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


class RestaurantModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "restaurants"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('active', 'discontinued')", name="status_is_valid"),
        CheckConstraint(
            "default_currency_code ~ '^[A-Z]{3}$'", name="default_currency_code_is_iso4217"
        ),
    )

    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # FK to `currencies.code` intentionally deferred until that reference
    # table exists -- mirrors `tenants.default_currency_code`'s own
    # established precedent (Sprint 3).
    default_currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")


class AddressModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "addresses"
    __table_args__ = (ulid_check_constraint("id"),)

    line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)


class BranchModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "branches"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "status IN ('opened', 'active', 'temporarily_closed', 'permanently_closed')",
            name="status_is_valid",
        ),
        Index("uq_branches_restaurant_id_name", "restaurant_id", "name", unique=True),
    )

    restaurant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("restaurants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    address_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    # Added by migration 0007 (Sprint 7 Step 2) for the operations
    # module's negative-inventory trigger; read (not written) by
    # anything in the restaurant module itself.
    allow_negative_stock: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class OperatingHoursModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "operating_hours"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="day_of_week_is_valid"),
        # opens_at > closes_at is a legitimate overnight window (closes the
        # following calendar day, e.g. a bar open 22:00-02:00) -- only
        # opens_at == closes_at (a zero-length window) is rejected. See
        # migration 0016 and ReplaceOperatingHoursUseCase's module
        # docstring.
        CheckConstraint("opens_at <> closes_at OR is_closed", name="opens_and_closes_are_distinct"),
    )

    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    opens_at: Mapped[time | None] = mapped_column(Time(), nullable=True)
    closes_at: Mapped[time | None] = mapped_column(Time(), nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class TableZoneModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "table_zones"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index("uq_table_zones_branch_id_name", "branch_id", "name", unique=True),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class TableModel(
    Base,
    ULIDPrimaryKeyMixin,
    TenantScopedMixin,
    BranchScopedMixin,
    TimestampMixin,
    SoftDeleteMixin,
    SyncVersionedMixin,
):
    __tablename__ = "tables"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("capacity > 0", name="capacity_is_positive"),
        CheckConstraint(
            "status IN ('available', 'occupied', 'reserved', 'cleaning')", name="status_is_valid"
        ),
        Index("ix_tables_branch_id_status", "branch_id", "status"),
        Index("uq_tables_branch_id_table_number", "branch_id", "table_number", unique=True),
    )

    table_zone_id: Mapped[str] = mapped_column(
        Text, ForeignKey("table_zones.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    table_number: Mapped[str] = mapped_column(Text, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="available")


class QRCodeModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "qr_codes"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('active', 'revoked')", name="status_is_valid"),
    )

    table_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tables.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Global uniqueness, not tenant-scoped -- resolved from an
    # unauthenticated guest request before tenant context is known.
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")


class MenuCategoryModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "menu_categories"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index("uq_menu_categories_restaurant_id_name", "restaurant_id", "name", unique=True),
    )

    restaurant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("restaurants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class MenuItemModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "menu_items"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("price_amount >= 0", name="price_amount_is_non_negative"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="currency_code_is_iso4217"),
    )

    menu_category_id: Mapped[str] = mapped_column(
        Text, ForeignKey("menu_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # FK added in migration 0008 (Sprint 7 Step 5), once Recipe existed.
    recipe_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=True
    )
    # Added in migration 0009 -- which KDS station this item routes to.
    station: Mapped[str] = mapped_column(Text, nullable=False, server_default="kitchen")


class ModifierGroupModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "modifier_groups"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("selection_type IN ('single', 'multiple')", name="selection_type_is_valid"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    selection_type: Mapped[str] = mapped_column(Text, nullable=False)


class ModifierModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "modifiers"
    __table_args__ = (ulid_check_constraint("id"),)

    modifier_group_id: Mapped[str] = mapped_column(
        Text, ForeignKey("modifier_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")


class MenuItemModifierGroupModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin):
    """A pure association row -- no independent audit weight, no
    ``TimestampMixin``/``SoftDeleteMixin`` beyond ``created_at``, matching
    ``RolePermissionModel``'s own classification in the RBAC module."""

    __tablename__ = "menu_item_modifier_groups"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index(
            "uq_menu_item_modifier_groups_menu_item_id_modifier_group_id",
            "menu_item_id",
            "modifier_group_id",
            unique=True,
        ),
    )

    menu_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modifier_group_id: Mapped[str] = mapped_column(
        Text, ForeignKey("modifier_groups.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )


class MenuItemBranchPriceModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "menu_item_branch_prices"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("price_amount >= 0", name="price_amount_is_non_negative"),
        CheckConstraint(
            "effective_from < effective_to OR effective_to IS NULL",
            name="effective_window_is_valid",
        ),
        Index("ix_menu_item_branch_prices_menu_item_id_branch_id", "menu_item_id", "branch_id"),
    )

    menu_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False
    )
    price_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True
    )


class MenuItemAvailabilityModel(
    Base, ULIDPrimaryKeyMixin, TenantScopedMixin, BranchScopedMixin, TimestampMixin, SoftDeleteMixin
):
    __tablename__ = "menu_item_availabilities"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "effective_from < effective_to OR effective_to IS NULL",
            name="effective_window_is_valid",
        ),
        Index("ix_menu_item_availabilities_menu_item_id_branch_id", "menu_item_id", "branch_id"),
    )

    menu_item_id: Mapped[str] = mapped_column(
        Text, ForeignKey("menu_items.id", ondelete="RESTRICT"), nullable=False
    )
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True
    )


class ReservationModel(
    Base,
    ULIDPrimaryKeyMixin,
    TenantScopedMixin,
    BranchScopedMixin,
    TimestampMixin,
    SoftDeleteMixin,
    SyncVersionedMixin,
):
    __tablename__ = "reservations"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("party_size > 0", name="party_size_is_positive"),
        CheckConstraint(
            "status IN ('requested', 'confirmed', 'seated', 'completed', 'no_show', 'canceled')",
            name="status_is_valid",
        ),
    )

    table_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tables.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    # Customer doesn't exist yet (future CRM Platform) -- reserved,
    # unpopulated, no FK, matching MenuItemModel.recipe_id's own pattern.
    customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="requested")


__all__ = [
    "AddressModel",
    "BranchModel",
    "MenuCategoryModel",
    "MenuItemAvailabilityModel",
    "MenuItemBranchPriceModel",
    "MenuItemModel",
    "MenuItemModifierGroupModel",
    "ModifierGroupModel",
    "ModifierModel",
    "OperatingHoursModel",
    "QRCodeModel",
    "ReservationModel",
    "RestaurantModel",
    "TableModel",
    "TableZoneModel",
]
