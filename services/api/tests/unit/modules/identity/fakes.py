"""In-memory test doubles for the identity module's ports.

Data Architecture v2.0 SS13: unit tests must run with no network/DB
access. These fakes implement the same ``Protocol`` interfaces the
SQLAlchemy repositories and Argon2/JWT services implement, so a use case
under test cannot tell the difference — and neither `sqlalchemy` nor
`argon2`/`jwt` needs to do any real work for these tests to be meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from restaurant_os_api.modules.identity.application.interfaces import (
    AccessTokenClaims,
    TokenDecodeError,
)
from restaurant_os_api.modules.identity.domain.entities import (
    OwnerActivationToken,
    Permission,
    Role,
    RolePermission,
    Session,
    Tenant,
    User,
    UserRole,
)
from restaurant_os_api.platform.events import DomainEvent


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

    async def count_active_for_tenant(self, tenant_id: str) -> int:
        return sum(
            1
            for u in self._users.values()
            if u.tenant_id == tenant_id and u.status.value == "active"
        )

    async def create(self, user: User) -> User:
        self._users[user.id] = user
        return user

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[User], int]:
        visible = [u for u in self._users.values() if u.tenant_id == tenant_id]
        visible.sort(key=lambda u: u.created_at, reverse=True)
        return visible[offset : offset + limit], len(visible)

    async def activate(self, tenant_id: str, user_id: str, *, password_hash: str) -> None:
        from restaurant_os_api.modules.identity.domain.entities import UserStatus

        user = self._users[user_id]
        user.password_hash = password_hash
        user.status = UserStatus.ACTIVE


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


class InMemoryOwnerActivationTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[str, OwnerActivationToken] = {}

    async def create(self, token: OwnerActivationToken) -> OwnerActivationToken:
        self.tokens[token.id] = token
        return token

    async def get_by_token_hash(self, token_hash: str) -> OwnerActivationToken | None:
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def mark_used(self, token_id: str, *, used_at: datetime) -> None:
        self.tokens[token_id].used_at = used_at

    async def get_latest_for_user(self, tenant_id: str, user_id: str) -> OwnerActivationToken | None:
        candidates = [
            t for t in self.tokens.values() if t.tenant_id == tenant_id and t.user_id == user_id
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.issued_at)


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
    decode_result: AccessTokenClaims | TokenDecodeError | None = None
    """Set by a test before calling ``decode_access_token`` -- either the
    claims to return, or a ``TokenDecodeError`` instance to raise. Left
    unset (``None``), decoding still raises ``NotImplementedError``,
    preserving the original "not exercised by login/refresh/logout"
    invariant for every test that never configures it."""

    def issue_access_token(self, claims: AccessTokenClaims) -> str:
        self.issued_claims.append(claims)
        return f"access-token::{claims.subject_user_id}::{claims.session_id}"

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        if self.decode_result is None:
            raise NotImplementedError("Not exercised by the login/refresh/logout use cases.")
        if isinstance(self.decode_result, TokenDecodeError):
            raise self.decode_result
        return self.decode_result

    def generate_refresh_token(self) -> str:
        self._refresh_counter += 1
        return f"refresh-token-{self._refresh_counter}"

    def hash_refresh_token(self, raw_token: str) -> str:
        return f"hashed::{raw_token}"


class InMemoryRoleRepository:
    def __init__(self, roles: dict[str, Role] | None = None) -> None:
        self._roles = roles or {}

    def _visible(self, tenant_id: str, role: Role) -> bool:
        return role.tenant_id is None or role.tenant_id == tenant_id

    async def get_by_id(self, tenant_id: str, role_id: str) -> Role | None:
        role = self._roles.get(role_id)
        if role is None or not self._visible(tenant_id, role):
            return None
        return role

    async def get_by_name(self, tenant_id: str, name: str) -> Role | None:
        for role in self._roles.values():
            if role.name == name and self._visible(tenant_id, role):
                return role
        return None

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Role], int]:
        visible = [r for r in self._roles.values() if self._visible(tenant_id, r)]
        visible.sort(key=lambda r: r.name)
        return visible[offset : offset + limit], len(visible)

    async def create(self, role: Role) -> Role:
        self._roles[role.id] = role
        return role

    async def update(self, role: Role) -> Role:
        self._roles[role.id] = role
        return role


class InMemoryPermissionRepository:
    def __init__(self, permissions: dict[str, Permission] | None = None) -> None:
        self._permissions = permissions or {}

    async def get_by_code(self, code: str) -> Permission | None:
        return self._permissions.get(code)

    async def list_active(self) -> list[Permission]:
        return [p for p in self._permissions.values() if p.is_active]


class InMemoryRolePermissionRepository:
    def __init__(self) -> None:
        # role_id -> {permission_code: RolePermission}
        self._by_role: dict[str, dict[str, RolePermission]] = {}
        self._active_permission_codes: frozenset[str] | None = None

    def set_active_permission_codes(self, codes: frozenset[str]) -> None:
        """Test-only hook: restrict which codes count as "active" when
        listing, mirroring the port's real semantics (retired
        Permission rows drop out of resolution even if a stale
        RolePermission row still references them). Defaults to
        treating every stored code as active."""
        self._active_permission_codes = codes

    async def list_permission_codes_for_role(self, role_id: str) -> frozenset[str]:
        codes = frozenset(self._by_role.get(role_id, {}).keys())
        if self._active_permission_codes is None:
            return codes
        return codes & self._active_permission_codes

    async def add(self, role_permission: RolePermission) -> RolePermission:
        self._by_role.setdefault(role_permission.role_id, {})[role_permission.permission_code] = (
            role_permission
        )
        return role_permission

    async def remove(self, role_id: str, permission_code: str) -> None:
        self._by_role.get(role_id, {}).pop(permission_code, None)

    async def replace_for_role(self, role_id: str, permission_codes: frozenset[str]) -> None:
        from datetime import UTC, datetime

        self._by_role[role_id] = {
            code: RolePermission(
                id=f"rp-{role_id}-{code}",
                role_id=role_id,
                permission_code=code,
                created_at=datetime.now(UTC),
            )
            for code in permission_codes
        }


class InMemoryUserRoleRepository:
    def __init__(self, user_roles: dict[str, UserRole] | None = None) -> None:
        self._user_roles = user_roles or {}
        self._revoked: set[str] = set()

    async def get_by_id(self, tenant_id: str, user_role_id: str) -> UserRole | None:
        ur = self._user_roles.get(user_role_id)
        if ur is None or ur.tenant_id != tenant_id or user_role_id in self._revoked:
            return None
        return ur

    async def list_active_for_user(self, tenant_id: str, user_id: str) -> list[UserRole]:
        return [
            ur
            for ur in self._user_roles.values()
            if ur.tenant_id == tenant_id and ur.user_id == user_id and ur.id not in self._revoked
        ]

    async def exists(
        self, tenant_id: str, user_id: str, role_id: str, branch_id: str | None
    ) -> bool:
        return any(
            ur.tenant_id == tenant_id
            and ur.user_id == user_id
            and ur.role_id == role_id
            and ur.branch_id == branch_id
            and ur.id not in self._revoked
            for ur in self._user_roles.values()
        )

    async def create(self, user_role: UserRole) -> UserRole:
        self._user_roles[user_role.id] = user_role
        return user_role

    async def revoke(self, tenant_id: str, user_role_id: str) -> UserRole | None:
        ur = self._user_roles.get(user_role_id)
        if ur is None or ur.tenant_id != tenant_id or user_role_id in self._revoked:
            return None
        self._revoked.add(user_role_id)
        return ur


@dataclass
class FakeOutboxWriter:
    """Records every published event in order; never touches a database."""

    published: list[tuple[str, DomainEvent]] = field(default_factory=list)

    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        self.published.append((tenant_id, event))
