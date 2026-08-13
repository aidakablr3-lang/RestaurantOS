"""RBAC domain events.

RBAC Foundation Architecture SS12: every RBAC-affecting mutation is a
security-relevant, audited fact. Framework-agnostic plain data
(Technical Architecture v2.0 SS2.2), each satisfying the
``platform.events.DomainEvent`` structural contract exactly like
``tenant_events.py`` — published through the existing ``OutboxWriter``
port, no new event infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class RoleCreated:
    role_id: str
    tenant_id: str | None
    name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "RoleCreated"
    aggregate_type: ClassVar[str] = "role"

    @property
    def aggregate_id(self) -> str:
        return self.role_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "roleId": self.role_id,
            "tenantId": self.tenant_id,
            "name": self.name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RoleRetired:
    role_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "RoleRetired"
    aggregate_type: ClassVar[str] = "role"

    @property
    def aggregate_id(self) -> str:
        return self.role_id

    def to_payload(self) -> dict[str, Any]:
        return {"roleId": self.role_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class PermissionGrantedToRole:
    role_id: str
    permission_code: str
    occurred_at: datetime

    event_type: ClassVar[str] = "PermissionGrantedToRole"
    aggregate_type: ClassVar[str] = "role"

    @property
    def aggregate_id(self) -> str:
        return self.role_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "roleId": self.role_id,
            "permissionCode": self.permission_code,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class PermissionRemovedFromRole:
    role_id: str
    permission_code: str
    occurred_at: datetime

    event_type: ClassVar[str] = "PermissionRemovedFromRole"
    aggregate_type: ClassVar[str] = "role"

    @property
    def aggregate_id(self) -> str:
        return self.role_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "roleId": self.role_id,
            "permissionCode": self.permission_code,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class UserRoleAssigned:
    user_role_id: str
    user_id: str
    role_id: str
    branch_id: str | None
    granted_by_user_id: str | None
    occurred_at: datetime

    event_type: ClassVar[str] = "UserRoleAssigned"
    aggregate_type: ClassVar[str] = "user_role"

    @property
    def aggregate_id(self) -> str:
        return self.user_role_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "userRoleId": self.user_role_id,
            "userId": self.user_id,
            "roleId": self.role_id,
            "branchId": self.branch_id,
            "grantedByUserId": self.granted_by_user_id,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class UserRoleRevoked:
    user_role_id: str
    user_id: str
    role_id: str
    branch_id: str | None
    occurred_at: datetime

    event_type: ClassVar[str] = "UserRoleRevoked"
    aggregate_type: ClassVar[str] = "user_role"

    @property
    def aggregate_id(self) -> str:
        return self.user_role_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "userRoleId": self.user_role_id,
            "userId": self.user_id,
            "roleId": self.role_id,
            "branchId": self.branch_id,
            "occurredAt": self.occurred_at.isoformat(),
        }
