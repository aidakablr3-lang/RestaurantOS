"""LedgerEntry entity -- append-only, written once, in the same
transaction as the fact it records (Data Architecture v2.0 Group I).
Every debit is matched by an equal credit within the same use case
call, never independently. ``ChartOfAccount`` itself is not modeled as
an entity here -- pure platform-seeded reference data (its own account
codes are the only thing referenced), matching how ``Permission``
isn't a domain entity in the identity module either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class LedgerEntryType(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


# The 8 platform-seeded chart_of_accounts codes (migration 0007) this
# module's ledger postings actually use.
class Account(StrEnum):
    CASH = "CASH"
    CARD_CLEARING = "CARD_CLEARING"
    SALES_REVENUE = "SALES_REVENUE"
    SALES_TAX_PAYABLE = "SALES_TAX_PAYABLE"
    TIPS_PAYABLE = "TIPS_PAYABLE"


@dataclass(slots=True)
class LedgerEntry:
    id: str
    tenant_id: str
    entry_type: LedgerEntryType
    account_code: str
    amount: Decimal
    currency_code: str
    created_at: datetime
    reference_type: str | None = None
    reference_id: str | None = None
