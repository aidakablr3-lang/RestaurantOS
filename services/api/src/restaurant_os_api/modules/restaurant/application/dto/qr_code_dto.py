"""Application-layer DTOs for QRCode management (Sprint 5 Step 4.6).

Scoped to the authenticated management routes only (``POST``/``GET
/api/v1/tables/{id}/qr-codes``) -- the unauthenticated resolution
endpoint (``GET /api/v1/qr/{token}``) is explicitly deferred to a
separate step per ADR 0001's own security requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class QRCodeDTO:
    id: str
    tenant_id: str
    branch_id: str
    table_id: str
    token: str
    status: str
    created_at: datetime
