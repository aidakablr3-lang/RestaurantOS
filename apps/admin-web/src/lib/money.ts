/**
 * Every money amount from the API arrives as a Decimal-precision
 * string (e.g. "270.0000") -- rendered raw, that's exactly the "four
 * decimals, no symbol" bug this fixes. One shared formatter so it
 * can't recur page by page the way it did: bill-print-view.tsx had
 * its own local version before this existed; the report page, orders
 * pages, bill detail page, and others all rendered the raw string
 * with no formatting at all.
 *
 * Only the two currencies real data in this codebase actually uses
 * get a symbol; anything else falls back to the old "amount CODE"
 * shape rather than guessing a wrong symbol.
 */

const CURRENCY_SYMBOLS: Record<string, string> = {
  INR: "₹",
  USD: "$",
}

export function formatMoney(amount: number | string, currencyCode: string): string {
  const formatted = Number(amount).toFixed(2)
  const symbol = CURRENCY_SYMBOLS[currencyCode]
  return symbol ? `${symbol}${formatted}` : `${formatted} ${currencyCode}`
}

/** For a value with no currency context available (e.g. a modifier's
 * price delta, which can be signed and isn't itself currency-tagged) --
 * fixes the decimal count only. */
export function formatAmount(amount: number | string): string {
  return Number(amount).toFixed(2)
}
