"""Application-layer DTO for owner activation (Phase 1 design doc SSA.4)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActivateOwnerRequestDTO:
    token: str
    new_password: str
