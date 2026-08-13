"""The qr_resolution_rate_limits table's SQLAlchemy model.

Sprint 5, Step 4.7. Deliberately does **not** use ``TenantScopedMixin``
-- this table has no ``tenant_id`` column at all (see the migration's
own docstring for why): it buckets an unauthenticated caller's request
*before* any tenant context can exist.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import Base, ULIDPrimaryKeyMixin
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


class RateLimitCounterModel(Base, ULIDPrimaryKeyMixin):
    __tablename__ = "qr_resolution_rate_limits"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "bucket_type IN ('ip', 'token')",
            name="ck_qr_resolution_rate_limits_bucket_type_is_valid",
        ),
        CheckConstraint(
            "total_count >= 0", name="ck_qr_resolution_rate_limits_total_count_is_non_negative"
        ),
        CheckConstraint(
            "failed_count >= 0", name="ck_qr_resolution_rate_limits_failed_count_is_non_negative"
        ),
        CheckConstraint(
            "failed_count <= total_count",
            name="ck_qr_resolution_rate_limits_failed_not_more_than_total",
        ),
        UniqueConstraint(
            "bucket_type",
            "bucket_key",
            "window_start",
            name="uq_qr_resolution_rate_limits_bucket_window",
        ),
    )

    bucket_type: Mapped[str] = mapped_column(Text, nullable=False)
    bucket_key: Mapped[str] = mapped_column(Text, nullable=False)
    window_start: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
