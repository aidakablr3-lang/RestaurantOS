/**
 * Mirrors modules/restaurant/presentation/api/v1/menu_import_router.py's
 * schemas (ExtractedMenuRowResponseSchema / CommitMenuImportRowRequestSchema).
 * Field names are camelCase on the wire.
 *
 * dietaryType/portionLabel/pricingUnit are extraction-only -- there is no
 * MenuItem column for them yet (see the backend DTO's own docstring for
 * why), so they exist here purely for the review grid to display.
 * portionLabel is the one exception carried through to commit: it's
 * folded into the persisted item name server-side.
 */

export type MenuImportConfidence = "high" | "medium" | "low"

export interface ExtractedMenuRow {
  category: string
  name: string
  rawPrice: string
  priceAmount: string | null
  confidence: MenuImportConfidence
  sourceImageIndex: number | null
  dietaryType: string | null
  portionLabel: string | null
  pricingUnit: string | null
  note: string | null
}

export interface MenuImportExtractResult {
  rows: ExtractedMenuRow[]
}

export interface MenuImportCommitRow {
  category: string
  name: string
  priceAmount: string
  portionLabel?: string | null
}

export interface CommitMenuImportResult {
  categoriesCreated: number
  itemsCreated: number
}
