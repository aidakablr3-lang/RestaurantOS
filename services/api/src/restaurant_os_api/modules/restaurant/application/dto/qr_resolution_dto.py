"""Application-layer DTO for QR Code resolution (Sprint 5 Step 4.7).

Deliberately its own DTO, not ``QRCodeDTO`` -- ADR 0001's resolution
response carries only three identifiers, never the token, status,
branch/tenant display data, or any other field the management-path
``QRCodeDTO`` exposes to an authenticated caller.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QRCodeResolutionDTO:
    tenant_id: str
    branch_id: str
    table_id: str
