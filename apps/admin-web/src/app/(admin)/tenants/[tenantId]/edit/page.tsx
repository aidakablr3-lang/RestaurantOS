"use client"

import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useTenant, useUpdateTenant } from "@/hooks/use-tenants"
import { ApiError } from "@/lib/api-client"
import { type EditTenantFormValues, editTenantSchema } from "@/lib/schemas/tenant"

export default function EditTenantPage() {
  const params = useParams<{ tenantId: string }>()
  const router = useRouter()
  const tenantId = params.tenantId

  const { data, isLoading, isError, error, refetch } = useTenant(tenantId)
  const tenant = data?.data
  const updateTenant = useUpdateTenant(tenantId)

  const form = useForm<EditTenantFormValues>({
    resolver: zodResolver(editTenantSchema),
    values: tenant
      ? {
          displayName: tenant.displayName,
          metadata:
            Object.keys(tenant.metadata).length > 0
              ? JSON.stringify(tenant.metadata, null, 2)
              : "",
        }
      : undefined,
  })

  async function onSubmit(values: EditTenantFormValues) {
    try {
      const metadata = values.metadata.trim()
        ? (JSON.parse(values.metadata) as Record<string, unknown>)
        : {}
      await updateTenant.mutateAsync({
        displayName: values.displayName,
        metadata,
      })
      toast.success("Tenant updated.")
      router.push(`/tenants/${tenantId}`)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to update tenant."
      )
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-72 max-w-lg" />
      </div>
    )
  }

  if (isError || !tenant) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {error instanceof ApiError
            ? error.message
            : "Failed to load this tenant."}
        </p>
        <Button variant="outline" className="mx-auto" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/tenants" className="hover:underline">
            Tenants
          </Link>{" "}
          /{" "}
          <Link href={`/tenants/${tenantId}`} className="hover:underline">
            {tenant.displayName}
          </Link>{" "}
          / Edit
        </p>
        <h1 className="text-xl font-semibold">Edit tenant</h1>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Tenant details</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="grid gap-4"
              noValidate
            >
              <FormField
                control={form.control}
                name="displayName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Display name</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="metadata"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Metadata</FormLabel>
                    <FormControl>
                      <Textarea
                        rows={8}
                        placeholder="{}"
                        className="font-mono text-xs"
                        {...field}
                      />
                    </FormControl>
                    <FormDescription>
                      Optional JSON object of tenant metadata.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="mt-2 flex gap-2">
                <Button type="submit" disabled={updateTenant.isPending}>
                  {updateTenant.isPending ? "Saving…" : "Save changes"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  render={<Link href={`/tenants/${tenantId}`} />}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  )
}
