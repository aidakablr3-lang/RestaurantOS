"""Pydantic request schema for POST /api/v1/owner-activation.

No response schema of its own -- success returns ``ApiResponse[None]``,
the same shape ``rbac_router.py``'s mutating-with-nothing-to-return
routes already use.
"""

from __future__ import annotations

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class ActivateOwnerRequestSchema(CamelModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=255)
