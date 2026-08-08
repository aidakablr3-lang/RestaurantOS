"""QRCode entity.

Restaurant Platform Architecture SS3.1: a table-scoped, guest-resolvable
identifier -- deliberately minimal, encoding only *which table*.
Modeled one-to-many against ``Table`` to preserve regeneration history
(a superseded code is revoked, a new row created, not overwritten) --
"regenerated/superseded" is therefore represented structurally, not as
a third status value; the architecture's own "Required fields" row
names only ``active``/``revoked``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.restaurant.domain.exceptions import (
    InvalidQRCodeStatusTransitionError,
)


class QRCodeStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(slots=True)
class QRCode:
    id: str
    tenant_id: str
    branch_id: str
    table_id: str
    token: str
    status: QRCodeStatus
    created_at: datetime

    def revoke(self) -> None:
        if self.status != QRCodeStatus.ACTIVE:
            raise InvalidQRCodeStatusTransitionError(
                self.id, self.status.value, QRCodeStatus.REVOKED.value
            )
        self.status = QRCodeStatus.REVOKED
