"use client"

/**
 * Upload -> extract -> review -> commit. Nothing reaches the database
 * until Commit -- extraction only ever populates local component state
 * (`rows`); the review grid mutates that same state directly.
 *
 * Uploaded files never leave the browser except in the one extract
 * request -- no server-side storage, no audit trail of the source
 * photos (a deliberate decision; see the design conversation). Object
 * URLs built from them for the review grid's "view source" dialog are
 * revoked on unmount/re-upload so they don't leak memory.
 */

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { FileIcon, ImageIcon, Loader2Icon, UploadIcon, XIcon } from "lucide-react"
import { toast } from "sonner"

import {
  type MenuImportGridRow,
  MenuImportReviewGrid,
  isRowValid,
  rowsFromExtraction,
} from "@/components/menu-import-review-grid"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/ui/page-header"
import { useMenuCategories } from "@/hooks/use-menu-categories"
import { useCommitMenuImport, useExtractMenuImport } from "@/hooks/use-menu-imports"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"

const ACCEPT =
  "image/jpeg,image/png,image/webp,image/gif,application/pdf,.csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

function isVisionFile(file: File): boolean {
  return file.type.startsWith("image/") || file.type === "application/pdf"
}

type Step = "upload" | "reviewing"

export default function MenuImportPage() {
  const params = useParams<{ restaurantId: string }>()
  const restaurantId = params.restaurantId
  const router = useRouter()

  const perms = usePermissionHelpers()
  const canManage = perms.hasTenantWide("menu.manage")

  const [step, setStep] = React.useState<Step>("upload")
  const [files, setFiles] = React.useState<File[]>([])
  const [rows, setRows] = React.useState<MenuImportGridRow[]>([])
  const [sourceImageUrls, setSourceImageUrls] = React.useState<string[]>([])

  const categoriesQuery = useMenuCategories(restaurantId, { offset: 0, limit: 100 })
  const existingCategoryNames = (categoriesQuery.data?.data ?? []).map((c) => c.name)

  const extractMenuImport = useExtractMenuImport(restaurantId)
  const commitMenuImport = useCommitMenuImport(restaurantId)

  React.useEffect(() => {
    return () => {
      for (const url of sourceImageUrls) URL.revokeObjectURL(url)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleFilesSelected(selected: FileList | null) {
    if (!selected) return
    setFiles((prev) => [...prev, ...Array.from(selected)])
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleExtract() {
    if (files.length === 0) return
    try {
      const result = await extractMenuImport.mutateAsync(files)
      const urls = files.filter(isVisionFile).map((f) => URL.createObjectURL(f))
      setSourceImageUrls(urls)
      setRows(rowsFromExtraction(result.data.rows))
      setStep("reviewing")
      if (result.data.rows.length === 0) {
        toast.warning("Nothing was extracted -- add rows manually below or try different files.")
      }
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to extract this menu.")
    }
  }

  const invalidCount = rows.filter((r) => !isRowValid(r)).length

  async function handleCommit() {
    if (rows.length === 0 || invalidCount > 0) return
    try {
      const result = await commitMenuImport.mutateAsync({
        rows: rows.map((r) => ({
          category: r.category.trim(),
          name: r.name.trim(),
          priceAmount: r.priceAmount.trim(),
          portionLabel: r.portionLabel.trim() || null,
        })),
        idempotencyKey: newIdempotencyKey(),
      })
      const { itemsCreated, categoriesCreated } = result.data
      toast.success(
        `Imported ${itemsCreated} item${itemsCreated === 1 ? "" : "s"}` +
          (categoriesCreated > 0
            ? ` into ${categoriesCreated} new categor${categoriesCreated === 1 ? "y" : "ies"}.`
            : ".")
      )
      router.push(`/restaurants/${restaurantId}/menu`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to commit this menu import.")
    }
  }

  if (!perms.isLoading && !canManage) {
    return <PermissionRestricted resource="menu import" />
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Import menu from photo"
        description="Upload photos, a PDF, or a spreadsheet of your menu -- review every row before anything is saved."
      />
      <p className="text-sm text-muted-foreground">
        <Link href={`/restaurants/${restaurantId}/menu`} className="hover:underline">
          Menu
        </Link>{" "}
        / Import
      </p>

      {step === "upload" ? (
        <Card>
          <CardHeader>
            <CardTitle>Upload</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center hover:bg-muted/40">
              <UploadIcon className="size-6 text-muted-foreground" />
              <span className="text-sm font-medium">Choose photos, a PDF, or a CSV/XLSX file</span>
              <span className="text-xs text-muted-foreground">
                A menu card is often several pages -- select as many photos as you need.
              </span>
              <input
                type="file"
                multiple
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => handleFilesSelected(e.target.files)}
              />
            </label>

            {files.length > 0 ? (
              <ul className="grid gap-2">
                {files.map((file, index) => (
                  <li
                    key={`${file.name}-${index}`}
                    className="flex items-center gap-2 rounded-lg border p-2 text-sm"
                  >
                    {file.type.startsWith("image/") ? (
                      <ImageIcon className="size-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="truncate">{file.name}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="ml-auto size-6"
                      aria-label={`Remove ${file.name}`}
                      onClick={() => removeFile(index)}
                    >
                      <XIcon className="size-3.5" />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : null}

            <Button
              type="button"
              className="w-fit"
              disabled={files.length === 0 || extractMenuImport.isPending}
              onClick={handleExtract}
            >
              {extractMenuImport.isPending ? (
                <>
                  <Loader2Icon className="animate-spin" />
                  Extracting…
                </>
              ) : (
                "Extract menu"
              )}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {rows.length} row{rows.length === 1 ? "" : "s"} extracted.
              {invalidCount > 0
                ? ` ${invalidCount} need${invalidCount === 1 ? "s" : ""} a category, name, and price before you can commit.`
                : ""}
            </p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => setStep("upload")}>
                Back to upload
              </Button>
              <Button
                type="button"
                disabled={rows.length === 0 || invalidCount > 0 || commitMenuImport.isPending}
                onClick={handleCommit}
              >
                {commitMenuImport.isPending ? (
                  <>
                    <Loader2Icon className="animate-spin" />
                    Committing…
                  </>
                ) : (
                  `Commit ${rows.length} item${rows.length === 1 ? "" : "s"}`
                )}
              </Button>
            </div>
          </div>

          <MenuImportReviewGrid
            rows={rows}
            onRowsChange={setRows}
            existingCategoryNames={existingCategoryNames}
            sourceImageUrls={sourceImageUrls}
          />
        </div>
      )}
    </div>
  )
}
