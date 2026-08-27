"""tenants.default_currency_code: enforce real ISO 4217 membership

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-27

A tenant was created with default_currency_code = "GST" -- not a
currency at all, a tax. Nothing in the stack caught it: the admin-web
form only checked "3 uppercase letters", the API's own request schema
only checked length, and this table's own CHECK constraint
(ck_tenants_default_currency_code_is_iso4217) only checked the same
regex (`~ '^[A-Z]{3}$'`) -- shape, never membership. The request
schema now validates against a real list
(restaurant_os_api.platform.currencies.ISO_4217_CURRENCIES); this
migration closes the same gap at the database layer, replacing the
regex with an explicit IN (...) list -- the same "fixed set of allowed
values" idiom migration 0001 already uses for tenant_tier/status on
this same table, not a new pattern.

The literal list below is a frozen snapshot of
platform/currencies.py's ISO_4217_CURRENCIES keys as of this
migration's authoring -- deliberately NOT imported from that module.
Importing live application code into a migration means this
migration's behavior would silently change if that module is ever
edited later, which defeats the point of a migration being a fixed
historical step. If the accepted currency set changes, write a new
migration that alters this constraint again; don't edit this one.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CHECK = "default_currency_code ~ '^[A-Z]{3}$'"

# 164 codes: ISO 4217's active list minus 11 real-but-not-a-tenant-
# currency entries (precious metals XAU/XAG/XPD/XPT, the IMF's XDR,
# four defunct European bond-market composite units XBA/XBB/XBC/XBD,
# and the two codes ISO 4217 itself defines as non-currencies XTS/XXX)
# -- see platform/currencies.py's own docstring for the full reasoning.
_NEW_CHECK = (
    "default_currency_code IN ('AED', 'AFN', 'ALL', 'AMD', 'AOA', 'ARS', 'AUD', 'AWG', "
    "'AZN', 'BAM', 'BBD', 'BDT', 'BHD', 'BIF', 'BMD', 'BND', 'BOB', 'BOV', 'BRL', "
    "'BSD', 'BTN', 'BWP', 'BYN', 'BZD', 'CAD', 'CDF', 'CHE', 'CHF', 'CHW', 'CLF', "
    "'CLP', 'CNY', 'COP', 'COU', 'CRC', 'CUP', 'CVE', 'CZK', 'DJF', 'DKK', 'DOP', "
    "'DZD', 'EGP', 'ERN', 'ETB', 'EUR', 'FJD', 'FKP', 'GBP', 'GEL', 'GHS', 'GIP', "
    "'GMD', 'GNF', 'GTQ', 'GYD', 'HKD', 'HNL', 'HTG', 'HUF', 'IDR', 'ILS', 'INR', "
    "'IQD', 'IRR', 'ISK', 'JMD', 'JOD', 'JPY', 'KES', 'KGS', 'KHR', 'KMF', 'KPW', "
    "'KRW', 'KWD', 'KYD', 'KZT', 'LAK', 'LBP', 'LKR', 'LRD', 'LSL', 'LYD', 'MAD', "
    "'MDL', 'MGA', 'MKD', 'MMK', 'MNT', 'MOP', 'MRU', 'MUR', 'MVR', 'MWK', 'MXN', "
    "'MXV', 'MYR', 'MZN', 'NAD', 'NGN', 'NIO', 'NOK', 'NPR', 'NZD', 'OMR', 'PAB', "
    "'PEN', 'PGK', 'PHP', 'PKR', 'PLN', 'PYG', 'QAR', 'RON', 'RSD', 'RUB', 'RWF', "
    "'SAR', 'SBD', 'SCR', 'SDG', 'SEK', 'SGD', 'SHP', 'SLE', 'SOS', 'SRD', 'SSP', "
    "'STN', 'SVC', 'SYP', 'SZL', 'THB', 'TJS', 'TMT', 'TND', 'TOP', 'TRY', 'TTD', "
    "'TWD', 'TZS', 'UAH', 'UGX', 'USD', 'USN', 'UYI', 'UYU', 'UYW', 'UZS', 'VED', "
    "'VES', 'VND', 'VUV', 'WST', 'XAF', 'XCD', 'XOF', 'XPF', 'XSU', 'YER', 'ZAR', "
    "'ZMW', 'ZWL')"
)

_CONSTRAINT_NAME = "ck_tenants_default_currency_code_is_iso4217"


def upgrade() -> None:
    op.drop_constraint(conv(_CONSTRAINT_NAME), "tenants", type_="check")
    op.create_check_constraint(conv(_CONSTRAINT_NAME), "tenants", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint(conv(_CONSTRAINT_NAME), "tenants", type_="check")
    op.create_check_constraint(conv(_CONSTRAINT_NAME), "tenants", _OLD_CHECK)
