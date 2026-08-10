"use client"

import * as React from "react"
import Link from "next/link"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { LayersIcon, PencilIcon, PlusIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
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
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
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
import { useCreateModifierGroup, useModifierGroups, useUpdateModifierGroup } from "@/hooks/use-modifier-groups"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type ModifierGroupFormValues, modifierGroupSchema } from "@/lib/schemas/modifier-group"
import type { ModifierGroup } from "@/types/modifier-group"

const PAGE_SIZE = 20

function ModifierGroupFormDialog({
  modifierGroup,
  trigger,
}: {
  modifierGroup?: ModifierGroup
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(modifierGroup)
  const createGroup = useCreateModifierGroup()
  const updateGroup = useUpdateModifierGroup(modifierGroup?.id ?? "")
  const mutation = isEdit ? updateGroup : createGroup

  const defaults: ModifierGroupFormValues = {
    name: modifierGroup?.name ?? "",
    selectionType: modifierGroup?.selectionType ?? "single",
  }

  const form = useForm<ModifierGroupFormValues>({
    resolver: zodResolver(modifierGroupSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: ModifierGroupFormValues) {
    try {
      if (isEdit) {
        await updateGroup.mutateAsync(values)
        toast.success("Modifier group updated.")
      } else {
        await createGroup.mutateAsync({ body: values, idempotencyKey: newIdempotencyKey() })
        toast.success("Modifier group created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to save this modifier group."
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit modifier group" : "Add modifier group"}</DialogTitle>
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
                    <Input placeholder="Toppings" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="selectionType"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Selection type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="single">Single (pick one)</SelectItem>
                      <SelectItem value="multiple">Multiple (pick any number)</SelectItem>
                    </SelectContent>
                  </Select>
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
                    : "Create group"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function ModifierGroupsPage() {
  const [offset, setOffset] = React.useState(0)
  const perms = usePermissionHelpers()
  const canRead = perms.hasTenantWide("menu.read")
  const canManage = perms.hasTenantWide("menu.manage")

  const { data, isLoading, isError, error, refetch } = useModifierGroups(
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canRead }
  )

  const modifierGroups = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Modifiers"
        description="Modifier groups (like Toppings or Spice Level) are shared across every restaurant and menu item in this tenant."
        actions={
          canManage ? (
            <ModifierGroupFormDialog
              trigger={
                <Button size="sm">
                  <PlusIcon />
                  Add group
                </Button>
              }
            />
          ) : undefined
        }
      />

      {!perms.isLoading && !canRead ? (
        <PermissionRestricted resource="modifier groups" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load modifier groups."}
          </p>
          <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="grid gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : modifierGroups.length === 0 ? (
        <EmptyState
          icon={LayersIcon}
          title="No modifier groups yet"
          description={
            canManage
              ? "Add a group like Toppings or Spice Level, then attach it to menu items."
              : "No modifier groups have been set up for this tenant yet."
          }
          action={
            canManage ? (
              <ModifierGroupFormDialog
                trigger={
                  <Button size="sm">
                    <PlusIcon />
                    Add group
                  </Button>
                }
              />
            ) : undefined
          }
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Selection type</TableHead>
                {canManage ? <TableHead className="w-20" /> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {modifierGroups.map((group) => (
                <TableRow key={group.id}>
                  <TableCell className="font-medium">
                    <Link href={`/modifier-groups/${group.id}`} className="hover:underline">
                      {group.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground capitalize">
                    {group.selectionType}
                  </TableCell>
                  {canManage ? (
                    <TableCell>
                      <ModifierGroupFormDialog
                        modifierGroup={group}
                        trigger={
                          <Button variant="ghost" size="icon" aria-label={`Edit ${group.name}`}>
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

      {meta && meta.total > 0 ? (
        <Pagination
          offset={meta.offset}
          limit={meta.limit}
          total={meta.total}
          onOffsetChange={setOffset}
        />
      ) : null}
    </div>
  )
}
