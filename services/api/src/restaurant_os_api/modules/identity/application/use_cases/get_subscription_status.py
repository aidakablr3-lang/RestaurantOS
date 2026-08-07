"""GetSubscriptionStatusUseCase."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import SubscriptionDTO
from restaurant_os_api.modules.identity.domain.exceptions import SubscriptionNotFoundError
from restaurant_os_api.modules.identity.domain.ports import SubscriptionRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetSubscriptionStatusUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        subscription_repository_factory: Callable[[AsyncSession], SubscriptionRepository],
    ) -> None:
        self._session_factory = session_factory
        self._subscription_repository_factory = subscription_repository_factory

    async def execute(self, tenant_id: str) -> SubscriptionDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            subscription_repo = self._subscription_repository_factory(uow.session)
            subscription = await subscription_repo.get_by_tenant_id(tenant_id)
        if subscription is None:
            raise SubscriptionNotFoundError(tenant_id)

        return SubscriptionDTO(
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
            is_active=subscription.is_active(),
            is_in_trial=subscription.is_in_trial(),
        )
