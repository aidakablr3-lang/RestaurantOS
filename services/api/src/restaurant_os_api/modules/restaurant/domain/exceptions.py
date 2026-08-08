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
