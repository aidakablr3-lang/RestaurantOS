"use client"

/**
 * The review grid is the important part of the menu-import flow, not
 * the extraction -- nothing here reaches the database until the owner
 * hits Commit on the wizard page that owns this grid's state. Every
 * field is editable so a wrong or missing extraction is just as
 * correctable as a low-confidence one.
 *
 * dietaryType/pricingUnit are shown and editable here but never sent to
 * commit (see types/menu-import.ts) -- there's no MenuItem column for
 * them yet, by deliberate decision, until a few real client menus are
 * seen. portionLabel IS sent -- it gets folded into the item name
 * server-side.
 *
 * Hand-rolled sorting/selection rather than a table library: the
 * installed @tanstack/react-table major version turned out to use a
 * ground-up-redesigned atoms/store API with no plain ColumnDef/
 * useReactTable surface, which would cost far more to adopt correctly
 * than this table's actual needs (sort by one column, checkbox select,
 * editable cells) justify -- and every other list in this app is
 * already a hand-rolled <Table> map with no grid library at all.
 */

import * as React from "react"
import { ArrowUpDownIcon, ImageIcon, PlusIcon, Trash2Icon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { suggestExistingCategory } from "@/lib/menu-import-helpers"
import type { ExtractedMenuRow, MenuImportConfidence } from "@/types/menu-import"

export interface MenuImportGridRow {
  id: string
  category: string
  name: string
  priceAmount: string
  portionLabel: string
  dietaryType: string
  pricingUnit: string
  confidence: MenuImportConfidence
  note: string | null
  sourceImageIndex: number | null
  rawPrice: string
}

let nextRowId = 0
function newRowId(): string {
  nextRowId += 1
  return `row-${nextRowId}`
}

export function rowsFromExtraction(rows: ExtractedMenuRow[]): MenuImportGridRow[] {
  return rows.map((row) => ({
    id: newRowId(),
    category: row.category,
    name: row.name,
    priceAmount: row.priceAmount ?? "",
    portionLabel: row.portionLabel ?? "",
    dietaryType: row.dietaryType ?? "unknown",
    pricingUnit: row.pricingUnit ?? "unknown",
    confidence: row.confidence,
    note: row.note,
    sourceImageIndex: row.sourceImageIndex,
    rawPrice: row.rawPrice,
  }))
}

export function blankRow(): MenuImportGridRow {
  return {
    id: newRowId(),
    category: "",
    name: "",
    priceAmount: "",
    portionLabel: "",
    dietaryType: "unknown",
    pricingUnit: "unknown",
    confidence: "high",
    note: null,
    sourceImageIndex: null,
    rawPrice: "",
  }
}

export function isRowValid(row: MenuImportGridRow): boolean {
  const price = Number(row.priceAmount)
  return (
    row.category.trim() !== "" && row.name.trim() !== "" && Number.isFinite(price) && price > 0
  )
}

type SortColumn = "category" | "name" | "priceAmount" | "confidence"

const CONFIDENCE_RANK: Record<MenuImportConfidence, number> = { low: 0, medium: 1, high: 2 }
const CONFIDENCE_VARIANT: Record<MenuImportConfidence, "secondary" | "outline" | "destructive"> = {
  high: "secondary",
  medium: "outline",
  low: "destructive",
}
const DIETARY_LABEL: Record<string, string> = { veg: "Veg", non_veg: "Non-veg", unknown: "Unknown" }
const UNIT_LABEL: Record<string, string> = { plate: "Plate", piece: "Piece", unknown: "Unknown" }

function CategoryCell({
  row,
  existingCategoryNames,
  onChange,
}: {
  row: MenuImportGridRow
  existingCategoryNames: string[]
  onChange: (value: string) => void
}) {
  const suggestion = suggestExistingCategory(row.category, existingCategoryNames)
  return (
    <div className="grid gap-1">
      <Input value={row.category} onChange={(e) => onChange(e.target.value)} className="h-8" />
      {suggestion ? (
        <button
          type="button"
          onClick={() => onChange(suggestion)}
          className="w-fit text-left text-xs text-muted-foreground underline decoration-dotted hover:text-foreground"
        >
          Did you mean &ldquo;{suggestion}&rdquo;?
        </button>
      ) : null}
    </div>
  )
}

function SortHeader({
  label,
  column,
  sortColumn,
  sortDirection,
  onSort,
}: {
  label: string
  column: SortColumn
  sortColumn: SortColumn | null
  sortDirection: "asc" | "desc"
  onSort: (column: SortColumn) => void
}) {
  return (
    <button type="button" className="flex items-center gap-1" onClick={() => onSort(column)}>
      {label}
      <ArrowUpDownIcon
        className={
          sortColumn === column
            ? "size-3 text-foreground"
            : "size-3 text-muted-foreground"
        }
      />
      {sortColumn === column ? (
        <span className="sr-only">{sortDirection === "asc" ? "ascending" : "descending"}</span>
      ) : null}
    </button>
  )
}

export function MenuImportReviewGrid({
  rows,
  onRowsChange,
  existingCategoryNames,
  sourceImageUrls,
}: {
  rows: MenuImportGridRow[]
  onRowsChange: (rows: MenuImportGridRow[]) => void
  existingCategoryNames: string[]
  sourceImageUrls: string[]
}) {
  const [sortColumn, setSortColumn] = React.useState<SortColumn | null>(null)
  const [sortDirection, setSortDirection] = React.useState<"asc" | "desc">("asc")
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set())
  const [previewSrc, setPreviewSrc] = React.useState<string | null>(null)
  const [bulkCategory, setBulkCategory] = React.useState("")
  const [bulkPrice, setBulkPrice] = React.useState("")

  function updateRow(id: string, patch: Partial<MenuImportGridRow>) {
    onRowsChange(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function deleteRow(id: string) {
    onRowsChange(rows.filter((r) => r.id !== id))
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  function toggleSort(column: SortColumn) {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"))
    } else {
      setSortColumn(column)
      setSortDirection("asc")
    }
  }

  function toggleRow(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? new Set(rows.map((r) => r.id)) : new Set())
  }

  function applyBulkCategory() {
    if (!bulkCategory.trim() || selectedIds.size === 0) return
    onRowsChange(
      rows.map((r) => (selectedIds.has(r.id) ? { ...r, category: bulkCategory.trim() } : r))
    )
    setBulkCategory("")
  }

  function applyBulkPrice() {
    if (!bulkPrice.trim() || selectedIds.size === 0) return
    onRowsChange(
      rows.map((r) => (selectedIds.has(r.id) ? { ...r, priceAmount: bulkPrice.trim() } : r))
    )
    setBulkPrice("")
  }

  const sortedRows = React.useMemo(() => {
    if (!sortColumn) return rows
    const factor = sortDirection === "asc" ? 1 : -1
    return [...rows].sort((a, b) => {
      if (sortColumn === "confidence") {
        return (CONFIDENCE_RANK[a.confidence] - CONFIDENCE_RANK[b.confidence]) * factor
      }
      if (sortColumn === "priceAmount") {
        return (Number(a.priceAmount || 0) - Number(b.priceAmount || 0)) * factor
      }
      return a[sortColumn].localeCompare(b[sortColumn]) * factor
    })
  }, [rows, sortColumn, sortDirection])

  const allSelected = rows.length > 0 && selectedIds.size === rows.length

  return (
    <div className="grid gap-3">
      {selectedIds.size > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/40 p-3">
          <span className="text-sm text-muted-foreground">{selectedIds.size} selected</span>
          <Input
            value={bulkCategory}
            onChange={(e) => setBulkCategory(e.target.value)}
            placeholder="Set category to…"
            className="h-8 w-48"
          />
          <Button type="button" size="sm" variant="outline" onClick={applyBulkCategory}>
            Apply category
          </Button>
          <Input
            value={bulkPrice}
            onChange={(e) => setBulkPrice(e.target.value)}
            placeholder="Set price to…"
            className="h-8 w-32"
            inputMode="decimal"
          />
          <Button type="button" size="sm" variant="outline" onClick={applyBulkPrice}>
            Apply price
          </Button>
        </div>
      ) : null}

      <div className="min-w-0 overflow-x-auto rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Checkbox
                  checked={allSelected}
                  onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  aria-label="Select all rows"
                />
              </TableHead>
              <TableHead>
                <SortHeader
                  label="Category"
                  column="category"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                />
              </TableHead>
              <TableHead>
                <SortHeader
                  label="Item name"
                  column="name"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                />
              </TableHead>
              <TableHead>
                <SortHeader
                  label="Price"
                  column="priceAmount"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                />
              </TableHead>
              <TableHead>Portion</TableHead>
              <TableHead>Dietary</TableHead>
              <TableHead>Unit</TableHead>
              <TableHead>
                <SortHeader
                  label="Confidence"
                  column="confidence"
                  sortColumn={sortColumn}
                  sortDirection={sortDirection}
                  onSort={toggleSort}
                />
              </TableHead>
              <TableHead>Source</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedRows.map((row) => {
              const src = row.sourceImageIndex !== null ? sourceImageUrls[row.sourceImageIndex] : undefined
              return (
                <TableRow
                  key={row.id}
                  className={
                    row.confidence === "low"
                      ? "border-l-2 border-l-destructive"
                      : row.confidence === "medium"
                        ? "border-l-2 border-l-amber-500"
                        : undefined
                  }
                >
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(row.id)}
                      onCheckedChange={(checked) => toggleRow(row.id, Boolean(checked))}
                      aria-label={`Select ${row.name || "row"}`}
                    />
                  </TableCell>
                  <TableCell>
                    <CategoryCell
                      row={row}
                      existingCategoryNames={existingCategoryNames}
                      onChange={(value) => updateRow(row.id, { category: value })}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={row.name}
                      onChange={(e) => updateRow(row.id, { name: e.target.value })}
                      className="h-8 min-w-40"
                    />
                  </TableCell>
                  <TableCell>
                    <div className="grid gap-0.5">
                      <Input
                        value={row.priceAmount}
                        onChange={(e) => updateRow(row.id, { priceAmount: e.target.value })}
                        className="h-8 w-24"
                        inputMode="decimal"
                      />
                      {row.rawPrice && row.rawPrice !== row.priceAmount ? (
                        <span
                          className="text-xs text-muted-foreground"
                          title="As printed on the source"
                        >
                          &ldquo;{row.rawPrice}&rdquo;
                        </span>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Input
                      value={row.portionLabel}
                      onChange={(e) => updateRow(row.id, { portionLabel: e.target.value })}
                      className="h-8 w-24"
                      placeholder="—"
                    />
                  </TableCell>
                  <TableCell>
                    <Select
                      value={row.dietaryType}
                      onValueChange={(v) => v && updateRow(row.id, { dietaryType: v })}
                      items={DIETARY_LABEL}
                    >
                      <SelectTrigger size="sm" className="w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(DIETARY_LABEL).map(([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Select
                      value={row.pricingUnit}
                      onValueChange={(v) => v && updateRow(row.id, { pricingUnit: v })}
                      items={UNIT_LABEL}
                    >
                      <SelectTrigger size="sm" className="w-24">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(UNIT_LABEL).map(([value, label]) => (
                          <SelectItem key={value} value={value}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <div className="grid max-w-40 gap-0.5">
                      <Badge variant={CONFIDENCE_VARIANT[row.confidence]} className="w-fit capitalize">
                        {row.confidence}
                      </Badge>
                      {row.note ? (
                        <span className="text-xs text-muted-foreground">{row.note}</span>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell>
                    {src ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        className="size-8"
                        aria-label={`View source photo ${row.sourceImageIndex! + 1}`}
                        onClick={() => setPreviewSrc(src)}
                      >
                        <ImageIcon className="size-4" />
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      aria-label={`Delete ${row.name || "row"}`}
                      onClick={() => deleteRow(row.id)}
                    >
                      <Trash2Icon className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-fit"
        onClick={() => onRowsChange([...rows, blankRow()])}
      >
        <PlusIcon />
        Add row
      </Button>

      <Dialog open={previewSrc !== null} onOpenChange={(open) => !open && setPreviewSrc(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Source photo</DialogTitle>
          </DialogHeader>
          {previewSrc ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={previewSrc}
              alt="Source menu page"
              className="max-h-[75vh] w-full object-contain"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
