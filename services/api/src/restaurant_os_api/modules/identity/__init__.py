"""Identity module: tenants, users, roles, permissions, sessions.

Owns authentication and the source-of-truth for authorization data.
Every other module depends on this one (Technical Architecture v2.0,
module relationship map) — it has no dependency on any other module.
"""
