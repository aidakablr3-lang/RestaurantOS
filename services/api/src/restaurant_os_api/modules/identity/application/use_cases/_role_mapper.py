"""Shared Role (domain entity) -> RoleDTO mapping.

Private to this package, same reasoning as ``_tenant_mapper.py``.
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.application.dto import RoleDTO
from restaurant_os_api.modules.identity.domain.entities import Role


def role_to_dto(role: Role) -> RoleDTO:
    return RoleDTO(
        id=role.id,
        tenant_id=role.tenant_id,
        name=role.name,
        description=role.description,
        default_scope=role.default_scope.value,
        is_system=role.is_system,
        is_active=role.is_active,
    )
