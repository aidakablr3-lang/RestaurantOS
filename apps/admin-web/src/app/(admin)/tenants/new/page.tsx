"use client"

import * as React from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { CheckIcon, CopyIcon } from "lucide-react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useCreateTenant } from "@/hooks/use-tenants"
import { ApiError } from "@/lib/api-client"
import { ISO_4217_CURRENCIES } from "@/lib/iso4217"
import { type CreateTenantFormValues, createTenantSchema } from "@/lib/schemas/tenant"

function OwnerActivationDialog({
  created,
  onClose,
}: {
  created: { tenantId: string; ownerEmail: string; token: string } | null
  onClose: () => void
}) {
  const [copied, setCopied] = React.useState(false)

  async function copyToken() {
    await navigator.clipboard.writeText(created?.token ?? "")
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Dialog open={created !== null} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tenant created</DialogTitle>
          <DialogDescription>
            Share this activation token with {created?.ownerEmail} over a channel you trust. It is
            shown only once here and cannot be retrieved again -- if it&apos;s lost, the owner
            can&apos;t activate their account through this token.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 rounded-lg border bg-muted/40 p-3">
          <code className="flex-1 overflow-x-auto text-sm">{created?.token}</code>
          <Button type="button" size="icon" variant="outline" onClick={copyToken}>
            {copied ? <CheckIcon className="text-green-600" /> : <CopyIcon />}
          </Button>
        </div>
        <DialogFooter>
          <Button type="button" onClick={onClose}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function CreateTenantPage() {
  const router = useRouter()
  const createTenant = useCreateTenant()
  const [created, setCreated] = React.useState<{
    tenantId: string
    ownerEmail: string
    token: string
  } | null>(null)

  const form = useForm<CreateTenantFormValues>({
    resolver: zodResolver(createTenantSchema),
    defaultValues: { legalName: "", displayName: "", defaultCurrencyCode: "INR", ownerEmail: "" },
  })

  async function onSubmit(values: CreateTenantFormValues) {
    try {
      const { data } = await createTenant.mutateAsync(values)
      toast.success("Tenant created.")
      if (data.ownerActivationToken) {
        setCreated({
          tenantId: data.id,
          ownerEmail: values.ownerEmail,
          token: data.ownerActivationToken,
        })
      } else {
        router.push(`/tenants/${data.id}`)
      }
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : "Failed to create tenant."
      )
    }
  }

  function closeActivationDialog() {
    if (created) router.push(`/tenants/${created.tenantId}`)
    setCreated(null)
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
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      items={Object.fromEntries(
                        Object.entries(ISO_4217_CURRENCIES).map(([code, name]) => [
                          code,
                          `${code} — ${name}`,
                        ])
                      )}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a currency" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {Object.entries(ISO_4217_CURRENCIES).map(([code, name]) => (
                          <SelectItem key={code} value={code}>
                            {code} — {name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Owners shouldn&apos;t be able to type anything here -- pick from a real
                      ISO 4217 currency.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="ownerEmail"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Owner email</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder="owner@acme.com" {...field} />
                    </FormControl>
                    <FormDescription>
                      The tenant&apos;s first Owner account -- invited, not yet active until they
                      use the activation token shown after creation.
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

      <OwnerActivationDialog created={created} onClose={closeActivationDialog} />
    </div>
  )
}
