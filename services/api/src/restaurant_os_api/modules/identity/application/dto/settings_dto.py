from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SystemSettingDTO:
    key: str
    value: dict[str, Any]
    branch_id: str | None


@dataclass(frozen=True, slots=True)
class UpdateSettingRequestDTO:
    tenant_id: str
    key: str
    value: dict[str, Any]
