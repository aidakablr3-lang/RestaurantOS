"""Shared User (domain entity) -> UserDTO mapping.

Private to this package, same reasoning as ``_role_mapper.py``.
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.application.dto import UserDTO
from restaurant_os_api.modules.identity.domain.entities import User


def user_to_dto(user: User, *, generated_password: str | None = None) -> UserDTO:
    return UserDTO(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        phone=user.phone,
        status=user.status.value,
        created_at=user.created_at.isoformat(),
        generated_password=generated_password,
    )
