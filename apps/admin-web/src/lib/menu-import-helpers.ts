// Fuzzy category matching for the menu-import review grid. This is a
// suggestion only -- it never renames a row's category itself. Commit
// resolves categories by exact, case-insensitive name match; a fuzzy
// hit here just offers the owner a "did you mean 'Veg Starters'?" pill
// to accept or ignore, so two near-identical spellings from different
// menu photos don't quietly become two separate categories without the
// owner ever seeing it happen.

function levenshteinDistance(a: string, b: string): number {
  const rows = a.length + 1
  const cols = b.length + 1
  const distances: number[][] = Array.from({ length: rows }, () => new Array<number>(cols).fill(0))

  for (let i = 0; i < rows; i++) distances[i]![0] = i
  for (let j = 0; j < cols; j++) distances[0]![j] = j

  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      distances[i]![j] = Math.min(
        distances[i - 1]![j]! + 1,
        distances[i]![j - 1]! + 1,
        distances[i - 1]![j - 1]! + cost
      )
    }
  }

  return distances[rows - 1]![cols - 1]!
}

function similarityRatio(a: string, b: string): number {
  if (a === b) return 1
  const maxLength = Math.max(a.length, b.length)
  if (maxLength === 0) return 1
  return 1 - levenshteinDistance(a, b) / maxLength
}

const SIMILARITY_THRESHOLD = 0.75

/**
 * Returns the closest existing category name if it's a near-but-not-exact
 * match for `name`, or null if there's an exact match already (nothing to
 * suggest) or nothing close enough.
 */
export function suggestExistingCategory(
  name: string,
  existingNames: string[]
): string | null {
  const normalized = name.trim().toLowerCase()
  if (!normalized) return null

  let best: { name: string; ratio: number } | null = null
  for (const existing of existingNames) {
    const existingNormalized = existing.trim().toLowerCase()
    if (existingNormalized === normalized) return null // exact match -- no suggestion needed
    const ratio = similarityRatio(normalized, existingNormalized)
    if (ratio >= SIMILARITY_THRESHOLD && (!best || ratio > best.ratio)) {
      best = { name: existing, ratio }
    }
  }
  return best?.name ?? null
}
