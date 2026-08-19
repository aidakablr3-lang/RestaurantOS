"""GenerateQrCodesStep -- Phase 1 design doc §A.7.

``CreateQRCodeUseCase`` issues one active code per table per call
("generates a new active code, revokes the prior one"), so this step
loops it once per ``ctx.table_ids`` -- the same "loop the single-item
use case" shape as ``CreateTableStep``. Both ``CreateQRCodeUseCase``
and ``ListQRCodesUseCase`` need an acting ``user_id`` for their
``resolve_and_authorize_branch`` check; the run's Owner
(``ctx.owner_id``, atomically created and role-granted by
``provision_tenant``) is used, matching the design doc's own §A.7
choice of ``granter_user_id=ctx.owner_id`` for the staff-creation
steps.

``verify()`` re-lists each table's QR codes and requires exactly one
``ACTIVE`` code per table -- "a code was generated at some point" is
not enough; a code later revoked out from under this step (with
nothing to replace it) must fail.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.restaurant.application.dto import QRCodeDTO
from restaurant_os_api.modules.restaurant.application.use_cases.create_qr_code import (
    CreateQRCodeUseCase,
)
from restaurant_os_api.modules.restaurant.application.use_cases.list_qr_codes import (
    ListQRCodesUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError

_ACTIVE = "active"


class GenerateQrCodesStepInput(BaseModel):
    pass


class GenerateQrCodesStep:
    def __init__(
        self,
        *,
        create_qr_code_use_case: CreateQRCodeUseCase,
        list_qr_codes_use_case: ListQRCodesUseCase,
    ) -> None:
        self.id = StepId.GENERATE_QR_CODES
        self.title = "Generate table QR codes"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_TABLE,)
        self.collect_schema = GenerateQrCodesStepInput
        self.autonomous = True

        self._create_qr_code_use_case = create_qr_code_use_case
        self._list_qr_codes_use_case = list_qr_codes_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: GenerateQrCodesStepInput, ctx: OnboardingRunContext
    ) -> tuple[QRCodeDTO, ...]:
        assert ctx.tenant_id is not None and ctx.owner_id is not None and ctx.table_ids, (
            "generate_qr_codes requires create_table first"
        )
        codes: list[QRCodeDTO] = []
        for table_id in ctx.table_ids:
            code = await self._create_qr_code_use_case.execute(ctx.tenant_id, ctx.owner_id, table_id)
            codes.append(code)
        return tuple(codes)

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.owner_id is None:
            return VerifyFailure(reason="tenant_id/owner_id not yet in context")
        if not ctx.table_ids:
            return VerifyFailure(reason="no table_ids recorded in context")

        active_counts: dict[str, int] = {}
        for table_id in ctx.table_ids:
            try:
                codes = await self._list_qr_codes_use_case.execute(
                    ctx.tenant_id, ctx.owner_id, table_id
                )
            except TableNotFoundError:
                return VerifyFailure(reason=f"table {table_id} not found on read-back")
            active_counts[table_id] = sum(1 for c in codes if c.status == _ACTIVE)

        missing = [tid for tid, count in active_counts.items() if count != 1]
        if missing:
            return VerifyFailure(
                reason=f"tables without exactly one active QR code: {missing}"
            )

        return VerifySuccess(
            evidence=f"LIST QR codes for {len(active_counts)} table(s) -> each has exactly 1 active"
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "GenerateQrCodesStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet."
        )
