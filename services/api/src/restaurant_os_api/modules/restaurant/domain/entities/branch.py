"""Branch entity.

Restaurant Platform Architecture SS3.1: a single physical location --
the unit the Blueprint's Branch Manager persona operates. ``tenant_id``
is denormalized from the parent ``Restaurant`` for RLS/query-filter
efficiency, the same denormalization pattern already used throughout
the catalogue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.restaurant.domain.exceptions import (
    InvalidBranchStatusTransitionError,
)


class BranchStatus(StrEnum):
    OPENED = "opened"
    ACTIVE = "active"
    TEMPORARILY_CLOSED = "temporarily_closed"
    PERMANENTLY_CLOSED = "permanently_closed"


@dataclass(slots=True)
class Branch:
    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    status: BranchStatus
    created_at: datetime
    address_id: str | None = None
    # Added by migration 0007 (Sprint 7 Step 2) for the operations
    # module's negative-inventory trigger. No route in this module sets
    # it yet -- read-only from the restaurant module's own perspective.
    allow_negative_stock: bool = False
    # GST registration is granted per legal entity *per state* -- the
    # legal entity lives on Restaurant, but only Branch (via its own
    # address) is granular enough to vary by state, so this lives here
    # rather than on Restaurant or Tenant. Branches in the same state
    # under the same Restaurant legitimately share one value.
    gstin: str | None = None
    # An invoice number series belongs to a GST registration, so this
    # must be unique per gstin, not per tenant -- two branches sharing
    # one GSTIN must not collide, but two branches with different (or
    # no) GSTINs may legitimately share a prefix. Auto-generated from
    # the branch name at creation, editable any time -- changing it
    # only affects invoices issued afterward; already-issued numbers
    # are frozen on their own Bill row, never derived live from this
    # field.
    invoice_prefix: str | None = None

    def activate(self) -> None:
        """Initial activation, following the branch's own setup flow --
        opened -> active, mirroring Tenant.activate()'s
        provisioning -> active shape."""
        self._transition_to(BranchStatus.ACTIVE, allowed_from=(BranchStatus.OPENED,))

    def close_temporarily(self) -> None:
        """SS7's ``POST /branches/{id}/close`` -- mirrors
        ``suspend``/``reactivate``'s existing sub-resource-verb pattern."""
        self._transition_to(BranchStatus.TEMPORARILY_CLOSED, allowed_from=(BranchStatus.ACTIVE,))

    def reopen(self) -> None:
        """SS7's ``POST /branches/{id}/reopen``."""
        self._transition_to(BranchStatus.ACTIVE, allowed_from=(BranchStatus.TEMPORARILY_CLOSED,))

    def close_permanently(self) -> None:
        self._transition_to(
            BranchStatus.PERMANENTLY_CLOSED,
            allowed_from=(BranchStatus.ACTIVE, BranchStatus.TEMPORARILY_CLOSED),
        )

    def _transition_to(
        self, new_status: BranchStatus, *, allowed_from: tuple[BranchStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidBranchStatusTransitionError(self.id, self.status.value, new_status.value)
        self.status = new_status
