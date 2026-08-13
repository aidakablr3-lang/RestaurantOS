"""Pydantic request/response schemas for Restaurant CRUD.

Matches ``modules.identity.presentation.schemas.tenant_schemas``'s
exact conventions: ``CamelModel`` for camelCase wire fields, ``Field``
constraints mirroring the backend ``CHECK``/length constraints
(``default_currency_code``'s 3-character bound mirrors
``tenants.default_currency_code``'s own schema precedent exactly).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateRestaurantRequestSchema(CamelModel):
    legal_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    default_currency_code: str = Field(..., min_length=3, max_length=3)


class UpdateRestaurantRequestSchema(CamelModel):
    legal_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    default_currency_code: str = Field(..., min_length=3, max_length=3)


class RestaurantResponseSchema(CamelModel):
    id: str
    tenant_id: str
    legal_name: str
    display_name: str
    default_currency_code: str
    status: str
    created_at: datetime
