"""Indian states and union territories, mapped to their GST state code.

The 2-digit prefix of a GSTIN is a state code (Notification 46/2017 --
Central Tax, as published on the GST portal), not part of the PAN --
``29ABCDE1234F1Z5`` means Karnataka regardless of what the PAN itself
encodes. This module is the one place that mapping lives:
``Address.state`` is validated against these names (mirroring how
``platform/currencies.py``'s ``ISO_4217_CURRENCIES`` backs
``tenants.default_currency_code`` -- migration 0015), and the same
mapping flags a branch whose ``Address.state`` doesn't match its own
``gstin``'s state code, a real, silent-until-audited data-entry
mistake otherwise (branches are entered by hand; a wrong state doesn't
break anything else, but does mean every invoice printed at that
branch understates or overstates POS/interstate GST treatment).

28 states + 8 union territories, current GST state codes as of this
writing. Codes are stable historical assignments (e.g. Andhra Pradesh
kept 28 after the 2014 Telangana split; Telangana was assigned 36) --
not resequenced when state boundaries change.
"""

from __future__ import annotations

INDIAN_STATE_GST_CODES: dict[str, str] = {
    "Jammu and Kashmir": "01",
    "Himachal Pradesh": "02",
    "Punjab": "03",
    "Chandigarh": "04",
    "Uttarakhand": "05",
    "Haryana": "06",
    "Delhi": "07",
    "Rajasthan": "08",
    "Uttar Pradesh": "09",
    "Bihar": "10",
    "Sikkim": "11",
    "Arunachal Pradesh": "12",
    "Nagaland": "13",
    "Manipur": "14",
    "Mizoram": "15",
    "Tripura": "16",
    "Meghalaya": "17",
    "Assam": "18",
    "West Bengal": "19",
    "Jharkhand": "20",
    "Odisha": "21",
    "Chhattisgarh": "22",
    "Madhya Pradesh": "23",
    "Gujarat": "24",
    "Dadra and Nagar Haveli and Daman and Diu": "26",
    "Maharashtra": "27",
    "Andhra Pradesh": "28",
    "Karnataka": "29",
    "Goa": "30",
    "Lakshadweep": "31",
    "Kerala": "32",
    "Tamil Nadu": "33",
    "Puducherry": "34",
    "Andaman and Nicobar Islands": "35",
    "Telangana": "36",
    "Ladakh": "38",
}
