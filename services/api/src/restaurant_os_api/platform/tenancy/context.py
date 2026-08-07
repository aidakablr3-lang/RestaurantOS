"""Tenant context — the single source of "which tenant is this request for."

Data Architecture v2.0 SS4.1: resolved once per request from the
authenticated principal (or, for the login endpoint itself, from the
login request's own tenant identifier — see LoginUserUseCase), and
threaded through the Unit of Work so every transaction issues the
``SET LOCAL app.tenant_id`` statement before any query runs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str
