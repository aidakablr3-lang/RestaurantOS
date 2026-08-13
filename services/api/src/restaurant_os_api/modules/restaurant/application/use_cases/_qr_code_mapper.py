from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import QRCodeDTO
from restaurant_os_api.modules.restaurant.domain.entities import QRCode


def qr_code_to_dto(qr_code: QRCode) -> QRCodeDTO:
    return QRCodeDTO(
        id=qr_code.id,
        tenant_id=qr_code.tenant_id,
        branch_id=qr_code.branch_id,
        table_id=qr_code.table_id,
        token=qr_code.token,
        status=qr_code.status.value,
        created_at=qr_code.created_at,
    )
