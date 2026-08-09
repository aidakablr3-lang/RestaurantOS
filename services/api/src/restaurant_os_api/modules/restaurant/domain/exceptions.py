"""Domain exceptions for the restaurant module.

Mirrors ``modules.identity.domain.exceptions``'s own shape exactly: no
HTTP concepts here (Technical Architecture v2.0 SS5.4), a stable
``error_code`` per exception. Restaurant Platform has no presentation
layer yet (Sprint 5 Step 3 is data-layer only), so these are not yet
registered in ``core/exceptions.py``'s ``_STATUS_BY_ERROR_CODE`` --
that registration is Step 5 (REST APIs) work, once routes exist to
raise them.
"""

from __future__ import annotations


class RestaurantDomainError(Exception):
    """Base class for every domain exception raised by the restaurant module."""

    error_code: str = "RESTAURANT_DOMAIN_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RestaurantNotFoundError(RestaurantDomainError):
    error_code = "RESTAURANT_NOT_FOUND"

    def __init__(self, restaurant_id: str) -> None:
        super().__init__(f"Restaurant '{restaurant_id}' does not exist.")
        self.restaurant_id = restaurant_id


class InvalidRestaurantStatusTransitionError(RestaurantDomainError):
    error_code = "INVALID_RESTAURANT_STATUS_TRANSITION"

    def __init__(self, restaurant_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Restaurant '{restaurant_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.restaurant_id = restaurant_id
        self.from_status = from_status
        self.to_status = to_status


class InvalidBranchStatusTransitionError(RestaurantDomainError):
    error_code = "INVALID_BRANCH_STATUS_TRANSITION"

    def __init__(self, branch_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Branch '{branch_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.branch_id = branch_id
        self.from_status = from_status
        self.to_status = to_status


class InvalidQRCodeStatusTransitionError(RestaurantDomainError):
    error_code = "INVALID_QR_CODE_STATUS_TRANSITION"

    def __init__(self, qr_code_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"QRCode '{qr_code_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.qr_code_id = qr_code_id
        self.from_status = from_status
        self.to_status = to_status


class BranchNotFoundError(RestaurantDomainError):
    error_code = "BRANCH_NOT_FOUND"

    def __init__(self, branch_id: str) -> None:
        super().__init__(f"Branch '{branch_id}' does not exist.")
        self.branch_id = branch_id


class BranchNameConflictError(RestaurantDomainError):
    """Mirrors the DB's own ``UNIQUE (restaurant_id, name)`` constraint
    (Restaurant Platform Architecture SS3.1) -- checked proactively so
    a duplicate name raises a clean domain error before ever reaching
    Postgres in the common case; the constraint itself remains the
    actual guarantee under a race."""

    error_code = "BRANCH_NAME_CONFLICT"

    def __init__(self, restaurant_id: str, name: str) -> None:
        super().__init__(
            f"A branch named '{name}' already exists for restaurant '{restaurant_id}'."
        )
        self.restaurant_id = restaurant_id
        self.name = name


class OperatingHoursConflictError(RestaurantDomainError):
    """A submitted weekly schedule contradicts itself for one
    ``day_of_week`` -- either an explicit ``is_closed`` row mixed with
    an open period for the same day, or two open periods that overlap.
    Architecture SS3.1 states this explicitly: "overlap validation is
    an application-layer concern, not a schema constraint" -- there is
    no DB constraint to mirror here (unlike ``BranchNameConflictError``),
    this exception *is* the validation."""

    error_code = "OPERATING_HOURS_CONFLICT"

    def __init__(self, day_of_week: int, detail: str) -> None:
        super().__init__(f"Operating hours for day {day_of_week} conflict: {detail}")
        self.day_of_week = day_of_week


class TableZoneNotFoundError(RestaurantDomainError):
    error_code = "TABLE_ZONE_NOT_FOUND"

    def __init__(self, table_zone_id: str) -> None:
        super().__init__(f"TableZone '{table_zone_id}' does not exist.")
        self.table_zone_id = table_zone_id


class TableZoneNameConflictError(RestaurantDomainError):
    """Mirrors the DB's own ``UNIQUE (branch_id, name)`` constraint
    (Restaurant Platform Architecture SS3.1's ``TableZone`` entry),
    checked proactively the same way ``BranchNameConflictError``
    checks ``UNIQUE (restaurant_id, name)``."""

    error_code = "TABLE_ZONE_NAME_CONFLICT"

    def __init__(self, branch_id: str, name: str) -> None:
        super().__init__(f"A table zone named '{name}' already exists for branch '{branch_id}'.")
        self.branch_id = branch_id
        self.name = name


class TableNotFoundError(RestaurantDomainError):
    error_code = "TABLE_NOT_FOUND"

    def __init__(self, table_id: str) -> None:
        super().__init__(f"Table '{table_id}' does not exist.")
        self.table_id = table_id


class TableNumberConflictError(RestaurantDomainError):
    """Mirrors the DB's own ``UNIQUE (branch_id, table_number)`` constraint
    (Restaurant Platform Architecture SS3.1's ``Table`` entry), checked
    proactively the same way ``BranchNameConflictError``/
    ``TableZoneNameConflictError`` check their own uniqueness
    constraints. Architecture SS7 names this exact error code as one of
    its own worked examples ("new codes following the established
    SCREAMING_SNAKE convention (BRANCH_NOT_FOUND,
    TABLE_NUMBER_ALREADY_EXISTS, MENU_ITEM_NOT_FOUND, ...)")."""

    error_code = "TABLE_NUMBER_ALREADY_EXISTS"

    def __init__(self, branch_id: str, table_number: str) -> None:
        super().__init__(
            f"A table numbered '{table_number}' already exists for branch '{branch_id}'."
        )
        self.branch_id = branch_id
        self.table_number = table_number


class MenuCategoryNotFoundError(RestaurantDomainError):
    error_code = "MENU_CATEGORY_NOT_FOUND"

    def __init__(self, menu_category_id: str) -> None:
        super().__init__(f"MenuCategory '{menu_category_id}' does not exist.")
        self.menu_category_id = menu_category_id


class MenuCategoryNameConflictError(RestaurantDomainError):
    """Mirrors the DB's own ``UNIQUE (restaurant_id, name)`` constraint
    (Restaurant Platform Architecture SS3.1's ``MenuCategory`` entry),
    checked proactively the same way ``BranchNameConflictError``/
    ``TableZoneNameConflictError`` check their own uniqueness
    constraints."""

    error_code = "MENU_CATEGORY_NAME_CONFLICT"

    def __init__(self, restaurant_id: str, name: str) -> None:
        super().__init__(
            f"A menu category named '{name}' already exists for restaurant '{restaurant_id}'."
        )
        self.restaurant_id = restaurant_id
        self.name = name


class MenuItemNotFoundError(RestaurantDomainError):
    """Architecture SS7 names this exact error code as one of its own
    worked examples ("new codes following the established
    SCREAMING_SNAKE convention (BRANCH_NOT_FOUND,
    TABLE_NUMBER_ALREADY_EXISTS, MENU_ITEM_NOT_FOUND, ...)")."""

    error_code = "MENU_ITEM_NOT_FOUND"

    def __init__(self, menu_item_id: str) -> None:
        super().__init__(f"MenuItem '{menu_item_id}' does not exist.")
        self.menu_item_id = menu_item_id


class ModifierGroupNotFoundError(RestaurantDomainError):
    """Architecture SS3.1's own ``ModifierGroup`` entry deliberately does
    not enforce name uniqueness ("a group named 'Size' legitimately
    repeats across unrelated item families"), so unlike
    ``MenuCategory``/``Branch``/``TableZone``/``Table``, there is no
    accompanying ``NameConflictError`` here."""

    error_code = "MODIFIER_GROUP_NOT_FOUND"

    def __init__(self, modifier_group_id: str) -> None:
        super().__init__(f"ModifierGroup '{modifier_group_id}' does not exist.")
        self.modifier_group_id = modifier_group_id


class ModifierNotFoundError(RestaurantDomainError):
    error_code = "MODIFIER_NOT_FOUND"

    def __init__(self, modifier_id: str) -> None:
        super().__init__(f"Modifier '{modifier_id}' does not exist.")
        self.modifier_id = modifier_id


class InvalidReservationStatusTransitionError(RestaurantDomainError):
    """A reasonable, standard reservation state machine
    (requested -> confirmed -> seated -> completed, with no_show/canceled
    as terminal exits from an earlier state) -- the architecture document
    specifies the six states but not their transition graph explicitly;
    this is a disclosed, derived interpretation, not an invented business
    rule beyond what the catalogue names."""

    error_code = "INVALID_RESERVATION_STATUS_TRANSITION"

    def __init__(self, reservation_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Reservation '{reservation_id}' cannot transition from '{from_status}' to '{to_status}'."
        )
        self.reservation_id = reservation_id
        self.from_status = from_status
        self.to_status = to_status
