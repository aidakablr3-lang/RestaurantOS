"""RolePermission entity.

RBAC Foundation Architecture SS4.3: join table granting a ``Permission``
to a ``Role``. A pure association row (Data Architecture v2.0 Group F's
own classification: "no independent audit weight — the Role edit itself
is audited") — no lifecycle methods, nothing to validate beyond what the
database's ``UNIQUE (role_id, permission_code)`` constraint and FK
integrity already guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class RolePermission:
    id: str
    role_id: str
    permission_code: str
    created_at: datetime
