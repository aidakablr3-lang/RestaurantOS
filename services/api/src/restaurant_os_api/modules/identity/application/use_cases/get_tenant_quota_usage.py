"""GetTenantQuotaUsageUseCase.

Reports quota *limits* (from the tenant's Subscription) alongside
*current usage* — but only for dimensions this module can actually
measure today. Sprint 4.1 scope boundary: active user count is real
(UserRepository.count_active_for_tenant); branch and monthly-order
counts are reported as ``None`` ("not yet available") because the
Restaurant and Orders modules that would own those counts do not exist
yet. This is read-only reporting, not enforcement — a future module
that needs to *block* an action at a quota limit consults the
``quota_enforcement_enabled`` feature flag and these same numbers
itself; this use case does not raise on over-quota, it just reports.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import TenantQuotaUsageDTO
from restaurant_os_api.modules.identity.domain.exceptions import SubscriptionNotFoundError
from restaurant_os_api.modules.identity.domain.ports import SubscriptionRepository, UserRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetTenantQuotaUsageUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        subscription_repository_factory: Callable[[AsyncSession], SubscriptionRepository],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
    ) -> None:
        self._session_factory = session_factory
        self._subscription_repository_factory = subscription_repository_factory
        self._user_repository_factory = user_repository_factory

    async def execute(self, tenant_id: str) -> TenantQuotaUsageDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            subscription_repo = self._subscription_repository_factory(uow.session)
            user_repo = self._user_repository_factory(uow.session)

            subscription = await subscription_repo.get_by_tenant_id(tenant_id)
            if subscription is None:
                raise SubscriptionNotFoundError(tenant_id)

            current_users = await user_repo.count_active_for_tenant(tenant_id)

        return TenantQuotaUsageDTO(
            max_branches=subscription.max_branches,
            max_users=subscription.max_users,
            max_monthly_orders=subscription.max_monthly_orders,
            current_users=current_users,
            current_branches=None,
            current_monthly_orders=None,
        )
