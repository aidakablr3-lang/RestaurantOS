/**
 * Mirrors services/api/src/restaurant_os_api/platform/indian_states.py's
 * INDIAN_STATE_GST_CODES exactly -- TypeScript can't import a Python
 * module, so this is kept in sync by hand. Keep both in sync if this
 * one ever changes (Indian state boundaries/codes change rarely).
 *
 * Backs both the branch edit form's State dropdown and the GSTIN/state
 * mismatch warning: a GSTIN's 2-digit prefix is a state code, so a
 * branch whose Address.state doesn't map to the same code as its own
 * gstin is very likely a data-entry mistake, not a real dual-state
 * business -- silent otherwise, since nothing else depends on state
 * matching gstin at write time.
 */
export const INDIAN_STATE_GST_CODES: Record<string, string> = {
  "Jammu and Kashmir": "01",
  "Himachal Pradesh": "02",
  Punjab: "03",
  Chandigarh: "04",
  Uttarakhand: "05",
  Haryana: "06",
  Delhi: "07",
  Rajasthan: "08",
  "Uttar Pradesh": "09",
  Bihar: "10",
  Sikkim: "11",
  "Arunachal Pradesh": "12",
  Nagaland: "13",
  Manipur: "14",
  Mizoram: "15",
  Tripura: "16",
  Meghalaya: "17",
  Assam: "18",
  "West Bengal": "19",
  Jharkhand: "20",
  Odisha: "21",
  Chhattisgarh: "22",
  "Madhya Pradesh": "23",
  Gujarat: "24",
  "Dadra and Nagar Haveli and Daman and Diu": "26",
  Maharashtra: "27",
  "Andhra Pradesh": "28",
  Karnataka: "29",
  Goa: "30",
  Lakshadweep: "31",
  Kerala: "32",
  "Tamil Nadu": "33",
  Puducherry: "34",
  "Andaman and Nicobar Islands": "35",
  Telangana: "36",
  Ladakh: "38",
}

/** State name for a GSTIN's 2-digit state-code prefix, or null if the GSTIN is too short/unknown. */
export function stateNameForGstin(gstin: string | null | undefined): string | null {
  if (!gstin || gstin.length < 2) return null
  const code = gstin.slice(0, 2)
  const entry = Object.entries(INDIAN_STATE_GST_CODES).find(([, c]) => c === code)
  return entry ? entry[0] : null
}
