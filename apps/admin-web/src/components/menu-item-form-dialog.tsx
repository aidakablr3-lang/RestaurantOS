"use client"

import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
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
import { useCreateMenuItem, useUpdateMenuItem } from "@/hooks/use-menu-items"
import { ApiError } from "@/lib/api-client"
import { newIdempotencyKey } from "@/lib/idempotency"
import { type MenuItemFormValues, menuItemSchema } from "@/lib/schemas/menu-item"
import type { MenuItem } from "@/types/menu-item"

export function MenuItemFormDialog({
  menuCategoryId,
  menuItem,
  trigger,
}: {
  menuCategoryId: string
  menuItem?: MenuItem
  trigger: React.ReactElement
}) {
  const [open, setOpen] = React.useState(false)
  const isEdit = Boolean(menuItem)
  const createMenuItem = useCreateMenuItem(menuCategoryId)
  const updateMenuItem = useUpdateMenuItem(menuCategoryId, menuItem?.id ?? "")
  const mutation = isEdit ? updateMenuItem : createMenuItem

  const defaults: MenuItemFormValues = {
    name: menuItem?.name ?? "",
    priceAmount: menuItem?.priceAmount ?? "0.00",
    currencyCode: menuItem?.currencyCode ?? "USD",
    isAvailable: menuItem?.isAvailable ?? true,
    displayOrder: menuItem?.displayOrder ?? 0,
  }

  const form = useForm<MenuItemFormValues>({
    resolver: zodResolver(menuItemSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: MenuItemFormValues) {
    try {
      if (isEdit) {
        await updateMenuItem.mutateAsync(values)
        toast.success("Menu item updated.")
      } else {
        await createMenuItem.mutateAsync({ body: values, idempotencyKey: newIdempotencyKey() })
        toast.success("Menu item created.")
      }
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to save this menu item.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={trigger} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit menu item" : "Add menu item"}</DialogTitle>
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
                    <Input placeholder="Spring Rolls" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="priceAmount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Price</FormLabel>
                    <FormControl>
                      <Input type="number" min={0} step={0.01} placeholder="8.99" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="currencyCode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Currency</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="USD"
                        maxLength={3}
                        {...field}
                        onChange={(event) => field.onChange(event.target.value.toUpperCase())}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="displayOrder"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display order</FormLabel>
                  <FormControl>
                    <Input type="number" min={0} step={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="isAvailable"
              render={({ field }) => (
                <FormItem>
                  <label className="flex items-center gap-2 text-sm">
                    <FormControl>
                      <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    Available
                  </label>
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
                    : "Create item"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
