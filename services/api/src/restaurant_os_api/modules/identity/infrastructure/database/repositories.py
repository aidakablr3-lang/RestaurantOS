"""SQLAlchemy implementations of the identity module's domain ports.

Technical Architecture v2.0 SS6.3: tenant-scoping and soft-delete
filtering are applied here, inside the repository, never left to
individual use cases to remember. Each method maps between the ORM
model (Infrastructure) and the domain entity (Domain) explicitly — the
Application layer never sees a SQLAlchemy model.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_os_api.modules.identity.domain.entities import (
    FeatureFlag,
    Session,
    Subscription,
    SubscriptionStatus,
    SystemSetting,
    Tenant,
    TenantDirectoryEntry,
    TenantStatus,
    TenantTier,
    User,
    UserStatus,
)
from restaurant_os_api.modules.identity.infrastructure.database.models import (
    FeatureFlagModel,
    SessionModel,
    SubscriptionModel,
    SystemSettingModel,
    TenantDirectoryEntryModel,
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
        metadata=dict(model.tenant_metadata),
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
        is_platform_admin=model.is_platform_admin,
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


def _subscription_from_model(model: SubscriptionModel) -> Subscription:
    return Subscription(
        id=model.id,
        tenant_id=model.tenant_id,
        plan_code=model.plan_code,
        status=SubscriptionStatus(model.status),
        current_period_end=model.current_period_end,
        created_at=model.created_at,
        trial_end=model.trial_end,
        next_billing_date=model.next_billing_date,
        grace_period_until=model.grace_period_until,
        max_branches=model.max_branches,
        max_users=model.max_users,
        max_monthly_orders=model.max_monthly_orders,
    )


def _system_setting_from_model(model: SystemSettingModel) -> SystemSetting:
    return SystemSetting(
        id=model.id,
        tenant_id=model.tenant_id,
        key=model.key,
        value=dict(model.value),
        created_at=model.created_at,
        branch_id=model.branch_id,
    )


def _feature_flag_from_model(model: FeatureFlagModel) -> FeatureFlag:
    return FeatureFlag(
        id=model.id,
        key=model.key,
        enabled=model.enabled,
        created_at=model.created_at,
        tenant_id=model.tenant_id,
        rollout_percentage=model.rollout_percentage,
        start_date=model.start_date,
        end_date=model.end_date,
    )


def _directory_entry_from_model(model: TenantDirectoryEntryModel) -> TenantDirectoryEntry:
    return TenantDirectoryEntry(
        tenant_id=model.tenant_id,
        tenant_tier=TenantTier(model.tenant_tier),
        shard_key=model.shard_key,
        connection_ref=model.connection_ref,
        status=TenantStatus(model.status),
        updated_at=model.updated_at,
    )


class SQLAlchemyTenantRepository:
    """Implements ``TenantRepository``.

    Unlike the tenant-owned repositories below, ``tenants`` itself
    carries no Row-Level Security policy (Data Architecture v2.0 SS5.2 —
    it is the scoping root, not scoped data), so these methods have no
    implicit tenant filter to apply.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        model = await self._session.get(TenantModel, tenant_id)
        return _tenant_from_model(model) if model is not None else None

    async def get_by_legal_name(self, legal_name: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.legal_name == legal_name)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _tenant_from_model(model) if model is not None else None

    async def create(self, tenant: Tenant) -> Tenant:
        model = TenantModel(
            id=tenant.id,
            legal_name=tenant.legal_name,
            display_name=tenant.display_name,
            tenant_tier=tenant.tenant_tier.value,
            status=tenant.status.value,
            default_currency_code=tenant.default_currency_code,
            tenant_metadata=tenant.metadata,
        )
        self._session.add(model)
        await self._session.flush()
        return _tenant_from_model(model)

    async def update(self, tenant: Tenant) -> Tenant:
        stmt = (
            update(TenantModel)
            .where(TenantModel.id == tenant.id)
            .values(
                legal_name=tenant.legal_name,
                display_name=tenant.display_name,
                status=tenant.status.value,
                tenant_metadata=tenant.metadata,
            )
        )
        await self._session.execute(stmt)
        return tenant

    async def list(
        self, *, offset: int, limit: int, status: TenantStatus | None = None
    ) -> tuple[list[Tenant], int]:
        filters = [TenantModel.status == status.value] if status is not None else []

        count_stmt = select(func.count()).select_from(TenantModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(TenantModel)
            .where(*filters)
            .order_by(TenantModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_tenant_from_model(m) for m in models], total


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


class SQLAlchemySubscriptionRepository:
    """Implements ``SubscriptionRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_tenant_id(self, tenant_id: str) -> Subscription | None:
        stmt = select(SubscriptionModel).where(SubscriptionModel.tenant_id == tenant_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _subscription_from_model(model) if model is not None else None

    async def create(self, subscription: Subscription) -> Subscription:
        model = SubscriptionModel(
            id=subscription.id,
            tenant_id=subscription.tenant_id,
            plan_code=subscription.plan_code,
            status=subscription.status.value,
            current_period_end=subscription.current_period_end,
            trial_end=subscription.trial_end,
            next_billing_date=subscription.next_billing_date,
            grace_period_until=subscription.grace_period_until,
            max_branches=subscription.max_branches,
            max_users=subscription.max_users,
            max_monthly_orders=subscription.max_monthly_orders,
        )
        self._session.add(model)
        await self._session.flush()
        return _subscription_from_model(model)

    async def update(self, subscription: Subscription) -> Subscription:
        stmt = (
            update(SubscriptionModel)
            .where(SubscriptionModel.id == subscription.id)
            .values(
                plan_code=subscription.plan_code,
                status=subscription.status.value,
                current_period_end=subscription.current_period_end,
                trial_end=subscription.trial_end,
                next_billing_date=subscription.next_billing_date,
                grace_period_until=subscription.grace_period_until,
                max_branches=subscription.max_branches,
                max_users=subscription.max_users,
                max_monthly_orders=subscription.max_monthly_orders,
            )
        )
        await self._session.execute(stmt)
        return subscription


class SQLAlchemySystemSettingRepository:
    """Implements ``SystemSettingRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_tenant(self, tenant_id: str) -> list[SystemSetting]:
        stmt = select(SystemSettingModel).where(SystemSettingModel.tenant_id == tenant_id)
        models = (await self._session.execute(stmt)).scalars().all()
        return [_system_setting_from_model(m) for m in models]

    async def get_by_key(self, tenant_id: str, key: str) -> SystemSetting | None:
        stmt = select(SystemSettingModel).where(
            SystemSettingModel.tenant_id == tenant_id,
            SystemSettingModel.key == key,
            SystemSettingModel.branch_id.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _system_setting_from_model(model) if model is not None else None

    async def upsert(self, setting: SystemSetting) -> SystemSetting:
        # `INSERT ... ON CONFLICT DO UPDATE` against the migration's
        # `UNIQUE NULLS NOT DISTINCT (tenant_id, branch_id, key)` index —
        # a single atomic statement rather than a separate
        # get-then-insert-or-update round trip.
        stmt = (
            pg_insert(SystemSettingModel)
            .values(
                id=setting.id,
                tenant_id=setting.tenant_id,
                branch_id=setting.branch_id,
                key=setting.key,
                value=setting.value,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "branch_id", "key"],
                set_={"value": setting.value},
            )
            .returning(SystemSettingModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        return _system_setting_from_model(model)


class SQLAlchemyFeatureFlagRepository:
    """Implements ``FeatureFlagRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_effective_for_tenant(self, tenant_id: str) -> list[FeatureFlag]:
        stmt = select(FeatureFlagModel).where(
            (FeatureFlagModel.tenant_id == tenant_id) | (FeatureFlagModel.tenant_id.is_(None))
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_feature_flag_from_model(m) for m in models]

    async def get_by_key(self, tenant_id: str, key: str) -> FeatureFlag | None:
        stmt = (
            select(FeatureFlagModel)
            .where(
                FeatureFlagModel.key == key,
                (FeatureFlagModel.tenant_id == tenant_id) | (FeatureFlagModel.tenant_id.is_(None)),
            )
            # A tenant-specific override sorts before the platform-wide
            # default of the same key (NULLS LAST puts the NULL-tenant
            # row second), so `.first()` below prefers the override.
            .order_by(FeatureFlagModel.tenant_id.isnot(None).desc())
        )
        model = (await self._session.execute(stmt)).scalars().first()
        return _feature_flag_from_model(model) if model is not None else None

    async def create(self, flag: FeatureFlag) -> FeatureFlag:
        model = FeatureFlagModel(
            id=flag.id,
            key=flag.key,
            tenant_id=flag.tenant_id,
            enabled=flag.enabled,
            rollout_percentage=flag.rollout_percentage,
            start_date=flag.start_date,
            end_date=flag.end_date,
        )
        self._session.add(model)
        await self._session.flush()
        return _feature_flag_from_model(model)


class SQLAlchemyTenantDirectoryRepository:
    """Implements ``TenantDirectoryRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_tenant_id(self, tenant_id: str) -> TenantDirectoryEntry | None:
        model = await self._session.get(TenantDirectoryEntryModel, tenant_id)
        return _directory_entry_from_model(model) if model is not None else None

    async def create(self, entry: TenantDirectoryEntry) -> TenantDirectoryEntry:
        model = TenantDirectoryEntryModel(
            tenant_id=entry.tenant_id,
            tenant_tier=entry.tenant_tier.value,
            shard_key=entry.shard_key,
            connection_ref=entry.connection_ref,
            status=entry.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _directory_entry_from_model(model)

    async def update_status(self, tenant_id: str, status: str) -> None:
        stmt = (
            update(TenantDirectoryEntryModel)
            .where(TenantDirectoryEntryModel.tenant_id == tenant_id)
            .values(status=status)
        )
        await self._session.execute(stmt)
