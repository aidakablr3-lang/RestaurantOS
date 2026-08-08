"""Address entity.

Restaurant Platform Architecture SS3.1: a normalized postal address,
reused by ``Branch`` today. Every field is individually nullable to
tolerate incomplete-onboarding states -- a Branch can exist with a
placeholder address during setup (the Blueprint's "a single-location
owner never has to configure branch concepts to get started"
principle). Shared shape, not a shared table via polymorphic
association (Data Architecture v1.0 ADR-D3) -- future platforms add
their own FK column to this same table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Address:
    id: str
    tenant_id: str
    created_at: datetime
    line1: str | None = None
    city: str | None = None
    country_code: str | None = None
    postal_code: str | None = None
