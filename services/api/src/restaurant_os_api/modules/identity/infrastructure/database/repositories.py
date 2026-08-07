"""SQLAlchemy implementations of the identity module's domain ports.

Technical Architecture v2.0 SS6.3: tenant-scoping and soft-delete
filtering are applied here, inside the repository, never left to
individual use cases to remember. Each method maps between the ORM
model (Infrastructure) and the domain entity (Domain) explicitly — the
Application layer never sees a SQLAlchemy model.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_os_api.modules.identity.domain.entities import (
    Session,
    Tenant,
    TenantStatus,
    TenantTier,
    User,
    UserStatus,
)
from restaurant_os_api.modules.identity.infrastructure.database.models import (
    SessionModel,
    TenantModel,
    UserModel,
)


def _tenant_from_model(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        legal_name=model.legal_name,
        display_name=model.display_name,
        tenant_tier=TenantTier(model.tenant_tier),
        status=TenantStatus(model.status),
        default_currency_code=model.default_currency_code,
        created_at=model.created_at,
    )


def _user_from_model(model: UserModel) -> User:
    return User(
        id=model.id,
        tenant_id=model.tenant_id,
        email=model.email,
        phone=model.phone,
        password_hash=model.password_hash,
        pin_hash=model.pin_hash,
        permission_version=model.permission_version,
        status=UserStatus(model.status),
        created_at=model.created_at,
    )


def _session_from_model(model: SessionModel) -> Session:
    return Session(
        id=model.id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        device_id=model.device_id,
        refresh_token_hash=model.refresh_token_hash,
        issued_at=model.issued_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
    )


class SQLAlchemyTenantRepository:
    """Implements ``TenantRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        model = await self._session.get(TenantModel, tenant_id)
        return _tenant_from_model(model) if model is not None else None


class SQLAlchemyUserRepository:
    """Implements ``UserRepository``.

    ``tenant_id`` is required on every method and is applied as an
    explicit filter here (Data Architecture v2.0 SS4.1's application-layer
    isolation layer) — this holds even though the ``users`` table also
    carries a Row-Level Security policy keyed to the same column; the two
    are independent, both-must-agree guarantees, not redundant.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, user_id: str) -> User | None:
        stmt = select(UserModel).where(
            UserModel.id == user_id,
            UserModel.tenant_id == tenant_id,
            UserModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _user_from_model(model) if model is not None else None

    async def get_by_email(self, tenant_id: str, email: str) -> User | None:
        stmt = select(UserModel).where(
            UserModel.tenant_id == tenant_id,
            UserModel.email == email,
            UserModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _user_from_model(model) if model is not None else None

    async def bump_permission_version(self, tenant_id: str, user_id: str) -> int:
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id, UserModel.tenant_id == tenant_id)
            .values(permission_version=UserModel.permission_version + 1)
            .returning(UserModel.permission_version)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()


class SQLAlchemySessionRepository:
    """Implements ``SessionRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session: Session) -> Session:
        model = SessionModel(
            id=session.id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            device_id=session.device_id,
            refresh_token_hash=session.refresh_token_hash,
            issued_at=session.issued_at,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _session_from_model(model)

    async def get_by_refresh_token_hash(
        self, tenant_id: str, refresh_token_hash: str
    ) -> Session | None:
        stmt = select(SessionModel).where(
            SessionModel.tenant_id == tenant_id,
            SessionModel.refresh_token_hash == refresh_token_hash,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _session_from_model(model) if model is not None else None

    async def revoke(self, session_id: str) -> None:
        stmt = (
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)

    async def revoke_all_for_user(self, user_id: str) -> None:
        stmt = (
            update(SessionModel)
            .where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
