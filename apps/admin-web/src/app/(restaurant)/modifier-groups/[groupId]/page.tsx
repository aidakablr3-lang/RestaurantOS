"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { PencilIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
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
import { useModifierGroup } from "@/hooks/use-modifier-groups"
import { useCreateModifier, useModifiers, useUpdateModifier } from "@/hooks/use-modifiers"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
// Modifier carries no currencyCode -- only the 2-decimal amount is
// formatted here, no currency symbol (matches priceDelta's sign-preserving semantics).
import { formatAmount } from "@/lib/money"
import { type ModifierFormValues, modifierSchema } from "@/lib/schemas/modifier"
import type { Modifier } from "@/types/modifier"

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 py-2 text-sm sm:grid-cols-[180px_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  )
}

function ModifierFormDialog({
  modifierGroupId,
  modifier,
  trigger,
}: {
  modifierGroupId: string
  modifier?: Modifier
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(modifier)
  const createModifier = useCreateModifier(modifierGroupId)
  const updateModifier = useUpdateModifier(modifierGroupId, modifier?.id ?? "")
  const mutation = isEdit ? updateModifier : createModifier

  const defaults: ModifierFormValues = {
    name: modifier?.name ?? "",
    priceDelta: modifier?.priceDelta ?? "0.00",
  }

  const form = useForm<ModifierFormValues>({
    resolver: zodResolver(modifierSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: ModifierFormValues) {
    try {
      if (isEdit) {
        await updateModifier.mutateAsync(values)
        toast.success("Modifier updated.")
      } else {
        await createModifier.mutateAsync({ body: values, idempotencyKey: newIdempotencyKey() })
        toast.success("Modifier created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to save this modifier.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit modifier" : "Add modifier"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="Extra cheese" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="priceDelta"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Price delta</FormLabel>
                  <FormControl>
                    <Input type="number" step={0.01} placeholder="1.50" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending
                  ? isEdit
                    ? "Saving…"
                    : "Creating…"
                  : isEdit
                    ? "Save changes"
                    : "Create modifier"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function ModifierGroupDetailPage() {
  const params = useParams<{ groupId: string }>()
  const router = useRouter()
  const groupId = params.groupId

  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("menu.read")
  const canManage = perms.hasTenantWide("menu.manage")
  const enabled = !perms.isLoading && canRead

  const groupQuery = useModifierGroup(groupId, { enabled })
  const group = groupQuery.data?.data

  const modifiersQuery = useModifiers(groupId, { enabled })
  const modifiers = modifiersQuery.data?.data ?? []

  if (perms.isLoading || groupQuery.isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!canRead) {
    return <PermissionRestricted resource="this modifier group" />
  }

  if (groupQuery.isError || !group) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {groupQuery.error instanceof ApiError
            ? groupQuery.error.message
            : "Failed to load this modifier group."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => groupQuery.refetch()}>
            Retry
          </Button>
          <Button variant="ghost" onClick={() => router.push("/modifier-groups")}>
            Back to modifier groups
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-xl font-semibold">{group.name}</h1>
        <p className="text-sm text-muted-foreground">
          <Link href="/modifier-groups" className="hover:underline">
            Modifiers
          </Link>{" "}
          / {group.name}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="divide-y">
          <DetailRow label="Name" value={group.name} />
          <DetailRow label="Selection type" value={<span className="capitalize">{group.selectionType}</span>} />
          <DetailRow label="Created" value={new Date(group.createdAt).toLocaleString()} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Modifiers</CardTitle>
          {canManage ? (
            <ModifierFormDialog
              modifierGroupId={groupId}
              trigger={
                <Button size="sm">
                  <PlusIcon />
                  Add modifier
                </Button>
              }
            />
          ) : null}
        </CardHeader>
        <CardContent>
          {modifiersQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : modifiersQuery.isError ? (
            <div className="grid gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
              <p className="text-sm text-destructive">
                {modifiersQuery.error instanceof ApiError
                  ? modifiersQuery.error.message
                  : "Failed to load modifiers."}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mx-auto"
                onClick={() => modifiersQuery.refetch()}
              >
                Retry
              </Button>
            </div>
          ) : modifiers.length === 0 ? (
            <EmptyState
              title="No modifiers yet"
              description={
                canManage
                  ? "Add options like Extra cheese or No onions to this group."
                  : "No modifiers have been added to this group yet."
              }
            />
          ) : (
            <div className="min-w-0 rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Price delta</TableHead>
                    {canManage ? <TableHead className="w-20" /> : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {modifiers.map((modifier) => (
                    <TableRow key={modifier.id}>
                      <TableCell className="font-medium">{modifier.name}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatAmount(modifier.priceDelta)}
                      </TableCell>
                      {canManage ? (
                        <TableCell>
                          <ModifierFormDialog
                            modifierGroupId={groupId}
                            modifier={modifier}
                            trigger={
                              <Button
                                variant="ghost"
                                size="icon"
                                aria-label={`Edit ${modifier.name}`}
                              >
                                <PencilIcon />
                              </Button>
                            }
                          />
                        </TableCell>
                      ) : null}
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
