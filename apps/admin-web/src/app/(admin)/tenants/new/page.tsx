"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
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
import { useCreateTenant } from "@/hooks/use-tenants"
import { ApiError } from "@/lib/api-client"
import { type CreateTenantFormValues, createTenantSchema } from "@/lib/schemas/tenant"

export default function CreateTenantPage() {
  const router = useRouter()
  const createTenant = useCreateTenant()

  const form = useForm<CreateTenantFormValues>({
    resolver: zodResolver(createTenantSchema),
    defaultValues: { legalName: "", displayName: "", defaultCurrencyCode: "" },
  })

  async function onSubmit(values: CreateTenantFormValues) {
    try {
      const { data } = await createTenant.mutateAsync(values)
      toast.success("Tenant created.")
      router.push(`/tenants/${data.id}`)
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to create tenant."
      )
    }
  }

  return (
    <div className="grid gap-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/tenants" className="hover:underline">
            Tenants
          </Link>{" "}
          / New
        </p>
        <h1 className="text-xl font-semibold">Create tenant</h1>
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
                name="legalName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Legal name</FormLabel>
                    <FormControl>
                      <Input placeholder="Acme Restaurants LLC" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="displayName"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Display name</FormLabel>
                    <FormControl>
                      <Input placeholder="Acme Restaurants" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="defaultCurrencyCode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Default currency</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="USD"
                        maxLength={3}
                        {...field}
                        onChange={(event) =>
                          field.onChange(event.target.value.toUpperCase())
                        }
                      />
                    </FormControl>
                    <FormDescription>
                      3-letter ISO 4217 currency code.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="mt-2 flex gap-2">
                <Button type="submit" disabled={createTenant.isPending}>
                  {createTenant.isPending ? "Creating…" : "Create tenant"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  render={<Link href="/tenants" />}
                  nativeButton={false}
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
