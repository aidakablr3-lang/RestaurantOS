"""Pydantic response schema for QRCode management (Sprint 5 Step 4.6).

No request schema exists -- ``POST /api/v1/tables/{id}/qr-codes``
takes no body (the table comes from the path, everything else is
generated), matching how ``close``/``reopen`` take no body either.
"""

from __future__ import annotations

from datetime import datetime

from restaurant_os_api.core.response import CamelModel


class QRCodeResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    table_id: str
    token: str
    status: str
    created_at: datetime
