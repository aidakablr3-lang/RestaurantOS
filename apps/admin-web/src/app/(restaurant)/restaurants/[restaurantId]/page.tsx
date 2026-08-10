"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PencilIcon, PlusIcon, StoreIcon, XCircleIcon } from "lucide-react"
import { toast } from "sonner"

import { BranchStatusBadge } from "@/components/branch-status-badge"
import { RestaurantStatusBadge } from "@/components/restaurant-status-badge"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
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
import { useCreateBranch, useDiscontinueRestaurant, useRestaurant } from "@/hooks/use-restaurants"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type BranchFormValues, branchSchema } from "@/lib/schemas/branch"

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 py-2 text-sm sm:grid-cols-[180px_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  )
}

function AddBranchDialog({ restaurantId }: { restaurantId: string }) {
  const [open, setOpen] = React.useState(false)
  const createBranch = useCreateBranch(restaurantId)

  const form = useForm<BranchFormValues>({
    resolver: zodResolver(branchSchema),
    defaultValues: { name: "", line1: "", city: "", countryCode: "", postalCode: "" },
  })

  async function onSubmit(values: BranchFormValues) {
    try {
      const hasAddress = values.line1 || values.city || values.countryCode || values.postalCode
      await createBranch.mutateAsync({
        body: {
          name: values.name,
          address: hasAddress
            ? {
                line1: values.line1 || null,
                city: values.city || null,
                countryCode: values.countryCode || null,
                postalCode: values.postalCode || null,
              }
            : null,
        },
        idempotencyKey: newIdempotencyKey(),
      })
      toast.success("Branch created.")
      form.reset()
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create branch.")
    }
  }

  function handleOpenChange(next: boolean) {
    // Reset on every open (not just after a successful submit) so a
    // cancelled attempt's draft values never leak into the next open.
    if (next) {
      form.reset()
    }
    setOpen(next)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add branch
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add branch</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch name</FormLabel>
                  <FormControl>
                    <Input placeholder="Downtown" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="line1"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Address line 1 (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="123 Main St" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="city"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>City (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="postalCode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Postal code (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="countryCode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Country code (optional)</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="US"
                      maxLength={2}
                      {...field}
                      onChange={(event) => field.onChange(event.target.value.toUpperCase())}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createBranch.isPending}>
                {createBranch.isPending ? "Creating…" : "Create branch"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function RestaurantDetailsPage() {
  const params = useParams<{ restaurantId: string }>()
  const router = useRouter()
  const restaurantId = params.restaurantId

  const { data, isLoading, isError, error, refetch } = useRestaurant(restaurantId)
  const restaurant = data?.data

  // GET /api/v1/branches has no restaurantId filter (it lists every branch
  // the caller can access) -- fetching a page and filtering client-side is
  // acceptable at pilot scale, but a real restaurantId query param would be
  // a genuine backend gap worth flagging if the branch count grows.
  const branchesQuery = useBranches({ offset: 0, limit: 100 })
  const branches = (branchesQuery.data?.data ?? []).filter(
    (branch) => branch.restaurantId === restaurantId
  )

  const discontinueRestaurant = useDiscontinueRestaurant(restaurantId)

  async function handleDiscontinue() {
    try {
      await discontinueRestaurant.mutateAsync(newIdempotencyKey())
      toast.success("Restaurant discontinued.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to discontinue restaurant.")
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (isError || !restaurant) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Failed to load this restaurant."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
          <Button variant="ghost" onClick={() => router.push("/restaurants")}>
            Back to restaurants
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
            <h1 className="text-xl font-semibold">{restaurant.displayName}</h1>
            <RestaurantStatusBadge status={restaurant.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            <Link href="/restaurants" className="hover:underline">
              Restaurants
            </Link>{" "}
            / {restaurant.displayName}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            render={<Link href={`/restaurants/${restaurant.id}/edit`} />}
            nativeButton={false}
          >
            <PencilIcon />
            Edit
          </Button>
          {restaurant.status === "active" ? (
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button variant="destructive" disabled={discontinueRestaurant.isPending}>
                    <XCircleIcon />
                    Discontinue
                  </Button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Discontinue this restaurant?</AlertDialogTitle>
                  <AlertDialogDescription>
                    {restaurant.displayName} will be marked discontinued. This does not
                    delete any data.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleDiscontinue}>
                    Discontinue restaurant
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="divide-y">
          <DetailRow label="Legal name" value={restaurant.legalName} />
          <DetailRow label="Display name" value={restaurant.displayName} />
          <DetailRow label="Default currency" value={restaurant.defaultCurrencyCode} />
          <DetailRow label="Status" value={<RestaurantStatusBadge status={restaurant.status} />} />
          <DetailRow
            label="Created"
            value={new Date(restaurant.createdAt).toLocaleString()}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Branches</CardTitle>
          <AddBranchDialog restaurantId={restaurant.id} />
        </CardHeader>
        <CardContent>
          {branchesQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : branches.length === 0 ? (
            <EmptyState
              icon={StoreIcon}
              title="No branches yet"
              description="Add a branch to start managing tables, hours, and reservations."
            />
          ) : (
            // No City column: GET /api/v1/branches never populates
            // address (see docs/DEVELOPMENT.md's Restaurant Platform
            // frontend section) -- the branch detail page shows it
            // correctly via GET /branches/{id}.
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {branches.map((branch) => (
                    <TableRow key={branch.id}>
                      <TableCell>
                        <Link
                          href={`/branches/${branch.id}`}
                          className="font-medium hover:underline"
                        >
                          {branch.name}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <BranchStatusBadge status={branch.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
