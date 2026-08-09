"""ResolveQRCodeUseCase.

Restaurant Platform Architecture SS7/SS11, ADR 0001's own "security
boundary the future QR-resolution endpoint MUST implement" -- Sprint 5
Step 4.7. Backs the sole unauthenticated route in this module,
``GET /api/v1/qr/{token}``.

**Enumeration protection (ADR 0001):** "token does not exist" and
"token exists but is revoked/inactive" collapse into exactly one
outcome here -- a plain ``None`` return, no distinguishing exception,
no distinguishing log level even. Both cases reach this same
``if qr_code is None or qr_code.status != QRCodeStatus.ACTIVE`` check
by way of the identical query (``get_by_token``, already filtering
``deleted_at IS NULL``), so there is no separate code path whose
existence alone could leak a timing or behavioral difference between
the two.

**No tenant context for the lookup itself:** ``qr_codes`` has no RLS
(ADR 0001), and ``UnitOfWork(session_factory)`` with no
``TenantContext`` is the same precedented pattern
``GetTenantUseCase``/``ListTenantsUseCase`` already use for queries
that must run before any tenant is known -- not a new mechanism.

**Referential consistency:** ``qr_code.branch_id``/``.table_id`` are
denormalized at *creation* time (``CreateQRCodeUseCase``, Step 4.6,
which itself resolves ``table_id -> branch_id`` before ever writing
the row) and are protected from drifting by the schema's own
``ON DELETE RESTRICT`` foreign keys -- there is nothing for this use
case to re-verify that the write path didn't already guarantee, so it
returns the row's own three identifiers directly rather than adding a
redundant read-back join.

**Abuse monitoring:** stdlib ``logging`` (this codebase's one existing
convention, ``core/exceptions.py``), not a new audit framework -- ADR
0001 itself says resolution attempts are "a distinct, higher-volume
signal better suited to request-level logging/monitoring than the
audit trail."
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import QRCodeResolutionDTO
from restaurant_os_api.modules.restaurant.domain.entities import QRCodeStatus
from restaurant_os_api.modules.restaurant.domain.ports import QRCodeRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.rate_limiting import QRResolutionRateLimiter, RateLimitExceededError

logger = logging.getLogger(__name__)


class ResolveQRCodeUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        qr_code_repository_factory: Callable[[AsyncSession], QRCodeRepository],
        rate_limiter: QRResolutionRateLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._qr_code_repository_factory = qr_code_repository_factory
        self._rate_limiter = rate_limiter

    async def execute(self, token: str, source_ip: str) -> QRCodeResolutionDTO | None:
        try:
            await self._rate_limiter.check(source_ip=source_ip, token=token)
        except RateLimitExceededError:
            logger.warning("QR resolution rate-limited before lookup: ip=%s", source_ip)
            raise

        async with UnitOfWork(self._session_factory) as uow:
            qr_code_repo = self._qr_code_repository_factory(uow.session)
            qr_code = await qr_code_repo.get_by_token(token)

        if qr_code is None or qr_code.status != QRCodeStatus.ACTIVE:
            logger.warning("QR resolution failed: ip=%s token=%s", source_ip, token)
            await self._rate_limiter.record_failure(source_ip=source_ip, token=token)
            return None

        logger.info(
            "QR resolution succeeded: ip=%s tenant_id=%s branch_id=%s table_id=%s",
            source_ip,
            qr_code.tenant_id,
            qr_code.branch_id,
            qr_code.table_id,
        )
        return QRCodeResolutionDTO(
            tenant_id=qr_code.tenant_id, branch_id=qr_code.branch_id, table_id=qr_code.table_id
        )
