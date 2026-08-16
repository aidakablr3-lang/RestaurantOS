"""Application-layer DTOs for User creation/listing.

Closes the "no user-creation use case exists" gap (``UserRepository``
has always had ``get_by_id``/``get_by_email`` but no ``create()``) --
the real ``POST /api/v1/users`` counterpart to the manually-run
``scripts/create_user.py`` operator script, for every account after a
tenant's first (the first Owner still has to go through the script:
no authenticated caller with ``roles.assign`` exists yet at that point).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateUserRequestDTO:
    creator_user_id: str
    email: str
    phone: str | None = None
    password: str | None = None


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: str
    tenant_id: str
    email: str | None
    phone: str | None
    status: str
    created_at: str
    # Only populated on the response to a *create* call, and only when
    # the caller didn't supply their own password -- shown exactly once
    # (the hash is one-way; there is no way to retrieve it again),
    # matching ``create_user.py``'s own "shown once" convention.
    generated_password: str | None = None


@dataclass(frozen=True, slots=True)
class UserListResultDTO:
    users: list[UserDTO]
    total: int
    offset: int
    limit: int
