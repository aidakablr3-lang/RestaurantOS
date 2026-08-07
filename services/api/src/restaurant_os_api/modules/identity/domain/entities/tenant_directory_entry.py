"""TenantDirectoryEntry — the Tenant Directory Service's record.

Data Architecture v2.0 SS4.4: resolves ``tenant_id`` to a shard/tier/
connection *before* a tenant-scoped database connection is even opened.
Scope note (see Sprint 4.1 plan): this sprint implements the directory
*data model* and resolution reads — every tenant resolves to today's
single connection. Actual multi-database connection routing (a second
physical shard) is explicitly future work; this table is what makes
introducing it later "add a row," not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from restaurant_os_api.modules.identity.domain.entities.tenant import TenantStatus, TenantTier


@dataclass(slots=True)
class TenantDirectoryEntry:
    tenant_id: str
    tenant_tier: TenantTier
    shard_key: str
    connection_ref: str
    status: TenantStatus
    updated_at: datetime
