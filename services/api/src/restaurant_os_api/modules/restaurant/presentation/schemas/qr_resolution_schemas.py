"""Response schema for QR Code resolution (Sprint 5 Step 4.7).

Deliberately **not** ``CamelModel`` -- every other endpoint in this
codebase wraps its response in the standard ``ApiResponse[T]`` envelope
with camelCase field names (Technical Architecture v2.0 SS5.6), but
ADR 0001 and architecture SS7 both specify this endpoint's response
literally: "returns only ``{tenant_id, branch_id, table_id}``, nothing
else." This is a distinct, minimal, unauthenticated bootstrap contract
for a not-yet-built external client (the future Customer/Guest
Platform), not the admin-web API -- so it gets its own plain schema
with exactly the field names the contract names, no envelope, no
camelCase conversion.
"""

from __future__ import annotations

from pydantic import BaseModel


class QRResolutionResponseSchema(BaseModel):
    tenant_id: str
    branch_id: str
    table_id: str
