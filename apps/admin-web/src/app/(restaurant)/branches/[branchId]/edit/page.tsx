"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { useBranch, useUpdateBranch } from "@/hooks/use-branches"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { ApiError } from "@/lib/api-client"
import { type BranchFormValues, branchSchema } from "@/lib/schemas/branch"

export default function EditBranchPage() {
  const params = useParams<{ branchId: string }>()
  const router = useRouter()
  const branchId = params.branchId

  const perms = usePermissionHelpers()
  const canManage = perms.hasAtBranch(branchId, "branch.manage")

  const { data, isLoading, isError, error, refetch } = useBranch(branchId)
  const branch = data?.data
  const updateBranch = useUpdateBranch(branchId)

  const form = useForm<BranchFormValues>({
    resolver: zodResolver(branchSchema),
    defaultValues: { name: "", line1: "", city: "", countryCode: "", postalCode: "", gstin: "" },
  })

  React.useEffect(() => {
    if (branch) {
      form.reset({
        name: branch.name,
        line1: branch.address?.line1 ?? "",
        city: branch.address?.city ?? "",
        countryCode: branch.address?.countryCode ?? "",
        postalCode: branch.address?.postalCode ?? "",
        gstin: branch.gstin ?? "",
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branch])

  async function onSubmit(values: BranchFormValues) {
    try {
      const hasAddress = values.line1 || values.city || values.countryCode || values.postalCode
      await updateBranch.mutateAsync({
        name: values.name,
        address: hasAddress
          ? {
              line1: values.line1 || null,
              city: values.city || null,
              countryCode: values.countryCode || null,
              postalCode: values.postalCode || null,
            }
          : null,
        gstin: values.gstin || null,
      })
      toast.success("Branch updated.")
      router.push(`/branches/${branchId}`)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to update branch.")
    }
  }

  if (perms.isLoading || isLoading) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full max-w-lg" />
      </div>
    )
  }

  if (!canManage) {
    return (
      <div className="grid gap-6">
        <h1 className="text-xl font-semibold">Edit branch</h1>
        <PermissionRestricted resource="branch editing" />
      </div>
    )
  }

  if (isError || !branch) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {error instanceof ApiError ? error.message : "Failed to load this branch."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
          <Button variant="ghost" onClick={() => router.push("/branches")}>
            Back to branches
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <Link href="/branches" className="hover:underline">
            Branches
          </Link>{" "}
          /{" "}
          <Link href={`/branches/${branchId}`} className="hover:underline">
            {branch.name}
          </Link>{" "}
          / Edit
        </p>
        <h1 className="text-xl font-semibold">Edit branch</h1>
      </div>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Branch details</CardTitle>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Branch name</FormLabel>
                    <FormControl>
                      <Input {...field} />
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
                    <FormLabel>Address line 1</FormLabel>
                    <FormControl>
                      <Input {...field} />
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
                      <FormLabel>City</FormLabel>
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
                      <FormLabel>Postal code</FormLabel>
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
                    <FormLabel>Country code</FormLabel>
                    <FormControl>
                      <Input
                        maxLength={2}
                        {...field}
                        onChange={(event) => field.onChange(event.target.value.toUpperCase())}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="gstin"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>GSTIN</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="29ABCDE1234F1Z5"
                        maxLength={15}
                        {...field}
                        onChange={(event) => field.onChange(event.target.value.toUpperCase())}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="mt-2 flex gap-2">
                <Button type="submit" disabled={updateBranch.isPending}>
                  {updateBranch.isPending ? "Saving…" : "Save changes"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  render={<Link href={`/branches/${branchId}`} />}
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
