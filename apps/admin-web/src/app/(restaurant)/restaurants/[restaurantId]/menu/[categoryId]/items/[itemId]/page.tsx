"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PencilIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { MenuItemFormDialog } from "@/components/menu-item-form-dialog"
import { PermissionRestricted } from "@/components/permission-restricted"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useBranches } from "@/hooks/use-branches"
import { useMenuCategory } from "@/hooks/use-menu-categories"
import {
  useCreateMenuItemAvailability,
  useCreateMenuItemBranchPrice,
  useMenuItem,
  useMenuItemAvailabilities,
  useMenuItemBranchPrices,
  useReplaceMenuItemModifierGroups,
} from "@/hooks/use-menu-items"
import { useModifierGroups } from "@/hooks/use-modifier-groups"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { formatMoney } from "@/lib/money"
import {
  type MenuItemAvailabilityFormValues,
  menuItemAvailabilitySchema,
} from "@/lib/schemas/menu-item-availability"
import {
  type MenuItemBranchPriceFormValues,
  menuItemBranchPriceSchema,
} from "@/lib/schemas/menu-item-branch-price"

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 py-2 text-sm sm:grid-cols-[180px_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  )
}

function toDatetimeLocal(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function ModifierGroupsCard({
  menuCategoryId,
  menuItemId,
  canManage,
}: {
  menuCategoryId: string
  menuItemId: string
  canManage: boolean
}) {
  const groupsQuery = useModifierGroups({ offset: 0, limit: 100 }, { enabled: true })
  const groups = groupsQuery.data?.data ?? []
  const replaceGroups = useReplaceMenuItemModifierGroups(menuCategoryId, menuItemId)

  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [lastSaved, setLastSaved] = React.useState<string[] | null>(null)

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleSave() {
    try {
      const result = await replaceGroups.mutateAsync({
        body: { modifierGroupIds: Array.from(selected) },
        idempotencyKey: newIdempotencyKey(),
      })
      setSelected(new Set(result.data.modifierGroupIds))
      setLastSaved(result.data.modifierGroupIds)
      toast.success("Modifier groups updated.")
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to update modifier groups."
      )
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Modifier groups</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3">
        <p className="text-xs text-muted-foreground">
          RestaurantOS&rsquo;s API can only <em>replace</em> a menu item&rsquo;s modifier groups, not report
          which ones are currently attached (no read endpoint exists for this yet -- a
          documented backend gap, not a frontend omission).{" "}
          {lastSaved
            ? "The checkboxes below reflect what this browser last saved."
            : "Select the complete set this item should have, including any already attached, before saving."}
        </p>
        {groupsQuery.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No modifier groups exist yet.{" "}
            <Link href="/modifier-groups" className="hover:underline">
              Create one
            </Link>{" "}
            first.
          </p>
        ) : (
          <div className="grid gap-2">
            {groups.map((group) => (
              <label key={group.id} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={selected.has(group.id)}
                  disabled={!canManage}
                  onCheckedChange={() => toggle(group.id)}
                />
                {group.name}
                <span className="text-xs text-muted-foreground">({group.selectionType})</span>
              </label>
            ))}
          </div>
        )}
        {canManage ? (
          <Button
            size="sm"
            className="w-fit"
            onClick={handleSave}
            disabled={replaceGroups.isPending || groups.length === 0}
          >
            {replaceGroups.isPending ? "Saving…" : "Save modifier groups"}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

function AddBranchPriceDialog({
  menuItemId,
  accessibleBranches,
}: {
  menuItemId: string
  accessibleBranches: { id: string; name: string }[]
}) {
  const [open, setOpen] = React.useState(false)
  const createPrice = useCreateMenuItemBranchPrice(menuItemId)

  const form = useForm<MenuItemBranchPriceFormValues>({
    resolver: zodResolver(menuItemBranchPriceSchema),
    defaultValues: { branchId: "", priceAmount: "0.00", effectiveFrom: "", effectiveTo: "" },
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset({ branchId: "", priceAmount: "0.00", effectiveFrom: "", effectiveTo: "" })
    setOpen(next)
  }

  async function onSubmit(values: MenuItemBranchPriceFormValues) {
    try {
      await createPrice.mutateAsync({
        body: {
          branchId: values.branchId,
          priceAmount: values.priceAmount,
          effectiveFrom: new Date(values.effectiveFrom).toISOString(),
          effectiveTo: values.effectiveTo ? new Date(values.effectiveTo).toISOString() : null,
        },
        idempotencyKey: newIdempotencyKey(),
      })
      toast.success("Branch price override created.")
      setOpen(false)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to create this price override."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm" disabled={accessibleBranches.length === 0}>
            <PlusIcon />
            Add price override
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add branch price override</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="branchId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose a branch" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {accessibleBranches.map((branch) => (
                        <SelectItem key={branch.id} value={branch.id}>
                          {branch.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="priceAmount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Price</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step={0.01} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="effectiveFrom"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Effective from</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="effectiveTo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Effective to (optional)</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={createPrice.isPending}>
                {createPrice.isPending ? "Creating…" : "Create override"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function AddAvailabilityDialog({
  menuItemId,
  accessibleBranches,
}: {
  menuItemId: string
  accessibleBranches: { id: string; name: string }[]
}) {
  const [open, setOpen] = React.useState(false)
  const createAvailability = useCreateMenuItemAvailability(menuItemId)

  const form = useForm<MenuItemAvailabilityFormValues>({
    resolver: zodResolver(menuItemAvailabilitySchema),
    defaultValues: { branchId: "", isAvailable: "true", effectiveFrom: "", effectiveTo: "" },
  })

  function handleOpenChange(next: boolean) {
    if (next)
      form.reset({ branchId: "", isAvailable: "true", effectiveFrom: "", effectiveTo: "" })
    setOpen(next)
  }

  async function onSubmit(values: MenuItemAvailabilityFormValues) {
    try {
      await createAvailability.mutateAsync({
        body: {
          branchId: values.branchId,
          isAvailable: values.isAvailable === "true",
          effectiveFrom: new Date(values.effectiveFrom).toISOString(),
          effectiveTo: values.effectiveTo ? new Date(values.effectiveTo).toISOString() : null,
        },
        idempotencyKey: newIdempotencyKey(),
      })
      toast.success("Branch availability override created.")
      setOpen(false)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to create this availability override."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm" disabled={accessibleBranches.length === 0}>
            <PlusIcon />
            Add availability override
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add branch availability override</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="branchId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choose a branch" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {accessibleBranches.map((branch) => (
                        <SelectItem key={branch.id} value={branch.id}>
                          {branch.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="isAvailable"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Availability</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="true">Available</SelectItem>
                      <SelectItem value="false">Unavailable</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="effectiveFrom"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Effective from</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="effectiveTo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Effective to (optional)</FormLabel>
                    <FormControl>
                      <Input type="datetime-local" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={createAvailability.isPending}>
                {createAvailability.isPending ? "Creating…" : "Create override"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function MenuItemDetailPage() {
  const params = useParams<{ restaurantId: string; categoryId: string; itemId: string }>()
  const router = useRouter()
  const { restaurantId, categoryId, itemId } = params

  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("menu.read")
  const canManage = perms.hasTenantWide("menu.manage")
  const canManageAnywhere = perms.hasAnywhere("menu.manage")
  const enabled = !perms.isLoading && canRead

  const categoryQuery = useMenuCategory(restaurantId, categoryId, { enabled })
  const category = categoryQuery.data?.data

  const itemQuery = useMenuItem(categoryId, itemId, { enabled })
  const item = itemQuery.data?.data

  // Fetched once and reused for both the branch-price/availability
  // "Branch" column joins and the add-override dialogs' Select options --
  // avoids an N+1 fetch per override row.
  const branchesQuery = useBranches({ offset: 0, limit: 100 }, { enabled })
  const branches = branchesQuery.data?.data ?? []
  const branchNameById = new Map(branches.map((branch) => [branch.id, branch.name]))
  const accessibleBranchIds = new Set(perms.accessibleBranchIds("menu.manage"))
  const accessibleBranches = branches
    .filter((branch) => accessibleBranchIds.has(branch.id))
    .map((branch) => ({ id: branch.id, name: branch.name }))

  const branchPricesQuery = useMenuItemBranchPrices(itemId, { enabled })
  const branchPrices = branchPricesQuery.data?.data ?? []

  const availabilitiesQuery = useMenuItemAvailabilities(itemId, { enabled })
  const availabilities = availabilitiesQuery.data?.data ?? []

  if (perms.isLoading || itemQuery.isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!canRead) {
    return <PermissionRestricted resource="this menu item" />
  }

  if (itemQuery.isError || !item) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {itemQuery.error instanceof ApiError
            ? itemQuery.error.message
            : "Failed to load this menu item."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => itemQuery.refetch()}>
            Retry
          </Button>
          <Button
            variant="ghost"
            onClick={() => router.push(`/restaurants/${restaurantId}/menu/${categoryId}`)}
          >
            Back to menu items
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{item.name}</h1>
            <Badge variant={item.isAvailable ? "secondary" : "outline"}>
              {item.isAvailable ? "Available" : "Unavailable"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            <Link href={`/restaurants/${restaurantId}`} className="hover:underline">
              Restaurant
            </Link>{" "}
            /{" "}
            <Link href={`/restaurants/${restaurantId}/menu`} className="hover:underline">
              Menu
            </Link>{" "}
            /{" "}
            <Link
              href={`/restaurants/${restaurantId}/menu/${categoryId}`}
              className="hover:underline"
            >
              {category?.name ?? categoryId}
            </Link>{" "}
            / {item.name}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="outline" render={<Link href={`/menu-items/${itemId}/recipe`} />} nativeButton={false}>
            Recipe
          </Button>
          {canManage ? (
            <MenuItemFormDialog
              menuCategoryId={categoryId}
              menuItem={item}
              trigger={
                <Button variant="outline">
                  <PencilIcon />
                  Edit
                </Button>
              }
            />
          ) : null}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="divide-y">
            <DetailRow label="Name" value={item.name} />
            <DetailRow label="Price" value={formatMoney(item.priceAmount, item.currencyCode)} />
            <DetailRow
              label="Station"
              value={
                <Badge variant="outline" className="capitalize">
                  {item.station}
                </Badge>
              }
            />
            <DetailRow
              label="Available"
              value={<Badge variant={item.isAvailable ? "secondary" : "outline"}>{item.isAvailable ? "Available" : "Unavailable"}</Badge>}
            />
            <DetailRow label="Display order" value={item.displayOrder} />
            <DetailRow label="Created" value={new Date(item.createdAt).toLocaleString()} />
          </CardContent>
        </Card>

        <ModifierGroupsCard menuCategoryId={categoryId} menuItemId={itemId} canManage={canManage} />

        <Card className="min-w-0">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Branch price overrides</CardTitle>
            {canManageAnywhere ? (
              <AddBranchPriceDialog menuItemId={itemId} accessibleBranches={accessibleBranches} />
            ) : null}
          </CardHeader>
          <CardContent>
            {branchPricesQuery.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : branchPricesQuery.isError ? (
              <p className="text-sm text-destructive">
                {branchPricesQuery.error instanceof ApiError
                  ? branchPricesQuery.error.message
                  : "Failed to load price overrides."}
              </p>
            ) : branchPrices.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No branch price overrides -- this item uses its base price everywhere.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Branch</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Effective</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {branchPrices.map((price) => (
                    <TableRow key={price.id}>
                      <TableCell>{branchNameById.get(price.branchId) ?? price.branchId}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatMoney(price.priceAmount, item.currencyCode)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {toDatetimeLocal(price.effectiveFrom).replace("T", " ")}
                        {price.effectiveTo
                          ? ` – ${toDatetimeLocal(price.effectiveTo).replace("T", " ")}`
                          : " – ongoing"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Branch availability overrides</CardTitle>
            {canManageAnywhere ? (
              <AddAvailabilityDialog menuItemId={itemId} accessibleBranches={accessibleBranches} />
            ) : null}
          </CardHeader>
          <CardContent>
            {availabilitiesQuery.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : availabilitiesQuery.isError ? (
              <p className="text-sm text-destructive">
                {availabilitiesQuery.error instanceof ApiError
                  ? availabilitiesQuery.error.message
                  : "Failed to load availability overrides."}
              </p>
            ) : availabilities.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No branch availability overrides -- this item uses its base availability
                everywhere.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Branch</TableHead>
                    <TableHead>Available</TableHead>
                    <TableHead>Effective</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {availabilities.map((availability) => (
                    <TableRow key={availability.id}>
                      <TableCell>
                        {branchNameById.get(availability.branchId) ?? availability.branchId}
                      </TableCell>
                      <TableCell>
                        <Badge variant={availability.isAvailable ? "secondary" : "outline"}>
                          {availability.isAvailable ? "Available" : "Unavailable"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {toDatetimeLocal(availability.effectiveFrom).replace("T", " ")}
                        {availability.effectiveTo
                          ? ` – ${toDatetimeLocal(availability.effectiveTo).replace("T", " ")}`
                          : " – ongoing"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
