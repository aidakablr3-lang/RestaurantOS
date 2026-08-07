"""In-memory test doubles for the identity module's ports.

Data Architecture v2.0 SS13: unit tests must run with no network/DB
access. These fakes implement the same ``Protocol`` interfaces the
SQLAlchemy repositories and Argon2/JWT services implement, so a use case
under test cannot tell the difference — and neither `sqlalchemy` nor
`argon2`/`jwt` needs to do any real work for these tests to be meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from restaurant_os_api.modules.identity.application.interfaces import AccessTokenClaims
from restaurant_os_api.modules.identity.domain.entities import Session, Tenant, User


class FakeAsyncSession:
    """Stands in for ``AsyncSession`` wherever ``UnitOfWork`` needs one.

    Only implements what ``UnitOfWork`` itself touches directly
    (``execute`` for the ``SET LOCAL`` statement, ``commit``/``rollback``/
    ``close``) — the in-memory repositories below never use this session
    at all, since they hold their own state.
    """

    def __init__(self) -> None:
        self.executed_statements: list[object] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def execute(self, statement: object, params: object = None) -> None:
        self.executed_statements.append((statement, params))

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


def fake_session_factory_returning(session: FakeAsyncSession):
    """Return a zero-arg callable matching ``async_sessionmaker``'s call shape."""

    def _factory() -> FakeAsyncSession:
        return session

    return _factory


class InMemoryTenantRepository:
    def __init__(self, tenants: dict[str, Tenant] | None = None) -> None:
        self._tenants = tenants or {}

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        return self._tenants.get(tenant_id)


class InMemoryUserRepository:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        # Keyed by user id; email lookups scan (fine at test scale).
        self._users = users or {}

    async def get_by_id(self, tenant_id: str, user_id: str) -> User | None:
        user = self._users.get(user_id)
        if user is None or user.tenant_id != tenant_id:
            return None
        return user

    async def get_by_email(self, tenant_id: str, email: str) -> User | None:
        for user in self._users.values():
            if user.tenant_id == tenant_id and user.email == email:
                return user
        return None

    async def bump_permission_version(self, tenant_id: str, user_id: str) -> int:
        user = self._users[user_id]
        user.permission_version += 1
        return user.permission_version


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    async def create(self, session: Session) -> Session:
        self.sessions[session.id] = session
        return session

    async def get_by_refresh_token_hash(
        self, tenant_id: str, refresh_token_hash: str
    ) -> Session | None:
        for session in self.sessions.values():
            if session.tenant_id == tenant_id and session.refresh_token_hash == refresh_token_hash:
                return session
        return None

    async def revoke(self, session_id: str) -> None:
        from datetime import UTC, datetime

        self.sessions[session_id].revoked_at = datetime.now(UTC)

    async def revoke_all_for_user(self, user_id: str) -> None:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        for session in self.sessions.values():
            if session.user_id == user_id and session.revoked_at is None:
                session.revoked_at = now


class FakePasswordHasher:
    """A trivial, fast, deterministic stand-in for Argon2id.

    Never used outside tests: the "hash" is reversible and predictable,
    which would be a critical vulnerability in production but is exactly
    what makes a fast, deterministic unit test possible.
    """

    def hash(self, plain_text: str) -> str:
        return f"hashed::{plain_text}"

    def verify(self, plain_text: str, hashed: str) -> bool:
        return hashed == f"hashed::{plain_text}"


@dataclass
class FakeTokenService:
    """A deterministic stand-in for JWTTokenService.

    ``issued_claims`` records every call to ``issue_access_token`` so
    tests can assert on exactly what was encoded (e.g., that no role or
    permission list ever appears — Technical Architecture v2.0 Group C).
    """

    issued_claims: list[AccessTokenClaims] = field(default_factory=list)
    _refresh_counter: int = 0

    def issue_access_token(self, claims: AccessTokenClaims) -> str:
        self.issued_claims.append(claims)
        return f"access-token::{claims.subject_user_id}::{claims.session_id}"

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        raise NotImplementedError("Not exercised by the login/refresh/logout use cases.")

    def generate_refresh_token(self) -> str:
        self._refresh_counter += 1
        return f"refresh-token-{self._refresh_counter}"

    def hash_refresh_token(self, raw_token: str) -> str:
        return f"hashed::{raw_token}"
