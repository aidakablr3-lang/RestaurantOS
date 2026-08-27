"""CreateTaxUseCase.

``POST /api/v1/taxes`` -- tenant-wide, mirrors ``CreateModifierGroupUseCase``'s
own flat, tenant-scoped shape (no branch dimension, gated
``require_permission("billing.manage")`` tenant-wide, not
``require_branch_permission``).

``rate`` is a fraction (0.09 for 9%), not a percent -- ``0-0.5`` is
enforced *here*, not just in ``CreateTaxRequestSchema``, because
``ConfigureTaxStepInput`` (the onboarding entry point) reaches this
same ``execute()`` with no Pydantic bound of its own. A production
incident stored ``rate=0.9`` for a "9%" tax (someone converted percent
to fraction by dividing by 10 instead of 100) -- 0.9 is a
legally-shaped fraction, so nothing upstream caught it. This bound
can't distinguish every possible mis-entry, but it makes the
overwhelming majority of them (anything read as a plausible restaurant
tax rate) impossible to store, regardless of which caller reaches this
use case.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.domain.entities import Tax
from restaurant_os_api.modules.operations.domain.exceptions import ImplausibleTaxRateError
from restaurant_os_api.modules.operations.domain.ports import TaxRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

_MAX_PLAUSIBLE_RATE = Decimal("0.5")


class CreateTaxUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tax_repository_factory: Callable[[AsyncSession], TaxRepository],
    ) -> None:
        self._session_factory = session_factory
        self._tax_repository_factory = tax_repository_factory

    async def execute(self, tenant_id: str, name: str, rate: str) -> Tax:
        parsed_rate = Decimal(rate)
        if parsed_rate < 0 or parsed_rate > _MAX_PLAUSIBLE_RATE:
            raise ImplausibleTaxRateError(rate)

        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tax_repo = self._tax_repository_factory(uow.session)
            tax = await tax_repo.create(
                Tax(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=name,
                    rate=parsed_rate,
                    is_active=True,
                    created_at=now,
                )
            )
        return tax
