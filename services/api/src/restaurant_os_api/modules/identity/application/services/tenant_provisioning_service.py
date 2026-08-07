"""TenantProvisioningService — orchestrates everything a new tenant needs.

Per the approved Sprint 4.1 plan: kept as its own service, separate from
``OnboardTenantUseCase``, so the use case stays a thin adapter (parse
request, call the service, shape the response) while every step of
"what does provisioning a tenant actually involve" lives in one place
that can grow (more seed data, more defaults) without the use case
itself changing shape.

Everything below runs inside **one** transaction: the tenant row, its
starter subscription, its Tenant Directory entry, its default feature
flag, and the ``TenantCreated`` outbox event either all commit together
or none do — Technical Architecture v2.0 Group B's atomicity guarantee,
applied to the multi-step provisioning workflow specifically because a
tenant left half-provisioned (a row in `tenants` with no subscription)
is a worse failure mode than the whole signup simply failing and being
retried.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.domain.entities import (
    FeatureFlag,
    Subscription,
    SubscriptionStatus,
    Tenant,
    TenantDirectoryEntry,
    TenantStatus,
    TenantTier,
)
from restaurant_os_api.modules.identity.domain.events import TenantCreated
from restaurant_os_api.modules.identity.domain.exceptions import TenantLegalNameConflictError
from restaurant_os_api.modules.identity.domain.ports import (
    FeatureFlagRepository,
    SubscriptionRepository,
    TenantDirectoryRepository,
    TenantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

# Sprint 4.1's one concrete "default feature flag provisioning" seed:
# every new tenant starts with quota enforcement (Commit 6's
# GetTenantQuotaUsageUseCase) explicitly on, as its own tenant-scoped
# flag rather than assumed unconditionally — so a support/ops workflow
# can flip it off per-tenant later (e.g., during a plan-migration
# window) without that being a special case in the quota-checking code
# itself. This is a real, load-bearing default, not a placeholder
# example — there are no other named platform features to seed yet.
_DEFAULT_FEATURE_FLAGS: tuple[str, ...] = ("quota_enforcement_enabled",)

_DEFAULT_TRIAL_DAYS = 14
_DEFAULT_PLAN_CODE = "starter"
_DEFAULT_SHARD_KEY = "shard-01"
_DEFAULT_CONNECTION_REF = "primary"


class TenantProvisioningService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
        subscription_repository_factory: Callable[[AsyncSession], SubscriptionRepository],
        feature_flag_repository_factory: Callable[[AsyncSession], FeatureFlagRepository],
        directory_repository_factory: Callable[[AsyncSession], TenantDirectoryRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory
        self._subscription_repository_factory = subscription_repository_factory
        self._feature_flag_repository_factory = feature_flag_repository_factory
        self._directory_repository_factory = directory_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def provision(
        self, *, legal_name: str, display_name: str, default_currency_code: str
    ) -> Tenant:
        # The new tenant's id is minted up front — every RLS-protected
        # insert below (subscription, feature flag) needs
        # `SET LOCAL app.tenant_id` set to *this* value from the start
        # of the transaction, before the `tenants` row (which carries no
        # RLS policy of its own — Data Architecture v2.0 SS5.2) is even
        # inserted.
        tenant_id = generate_ulid()
        now = datetime.now(UTC)

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            subscription_repo = self._subscription_repository_factory(uow.session)
            flag_repo = self._feature_flag_repository_factory(uow.session)
            directory_repo = self._directory_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            if await tenant_repo.get_by_legal_name(legal_name) is not None:
                raise TenantLegalNameConflictError(legal_name)

            tenant = Tenant(
                id=tenant_id,
                legal_name=legal_name,
                display_name=display_name,
                tenant_tier=TenantTier.SHARED,
                status=TenantStatus.PROVISIONING,
                default_currency_code=default_currency_code,
                created_at=now,
            )
            tenant = await tenant_repo.create(tenant)

            trial_end = now + timedelta(days=_DEFAULT_TRIAL_DAYS)
            subscription = Subscription(
                id=generate_ulid(),
                tenant_id=tenant_id,
                plan_code=_DEFAULT_PLAN_CODE,
                status=SubscriptionStatus.TRIALING,
                current_period_end=trial_end,
                created_at=now,
                trial_end=trial_end,
                next_billing_date=trial_end,
            )
            await subscription_repo.create(subscription)

            await directory_repo.create(
                TenantDirectoryEntry(
                    tenant_id=tenant_id,
                    tenant_tier=tenant.tenant_tier,
                    shard_key=_DEFAULT_SHARD_KEY,
                    connection_ref=_DEFAULT_CONNECTION_REF,
                    status=tenant.status,
                    updated_at=now,
                )
            )

            for flag_key in _DEFAULT_FEATURE_FLAGS:
                await flag_repo.create(
                    FeatureFlag(
                        id=generate_ulid(),
                        key=flag_key,
                        enabled=True,
                        created_at=now,
                        tenant_id=tenant_id,
                        rollout_percentage=100,
                    )
                )

            tenant.activate()
            tenant = await tenant_repo.update(tenant)
            await directory_repo.update_status(tenant_id, tenant.status.value)

            await outbox.publish(
                tenant_id,
                TenantCreated(
                    tenant_id=tenant_id,
                    legal_name=tenant.legal_name,
                    display_name=tenant.display_name,
                    tenant_tier=tenant.tenant_tier.value,
                    occurred_at=now,
                ),
            )

        return tenant
