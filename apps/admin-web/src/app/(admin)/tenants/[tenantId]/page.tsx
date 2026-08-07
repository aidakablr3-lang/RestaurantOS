"use client"

import * as React from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { PencilIcon, PlayIcon, PauseIcon } from "lucide-react"
import { toast } from "sonner"

import { TenantStatusBadge } from "@/components/tenant-status-badge"
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
import { Skeleton } from "@/components/ui/skeleton"
import {
  useReactivateTenant,
  useSuspendTenant,
  useTenant,
} from "@/hooks/use-tenants"
import { ApiError } from "@/lib/api-client"

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 py-2 text-sm sm:grid-cols-[180px_1fr]">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium break-words">{value}</span>
    </div>
  )
}

export default function TenantDetailsPage() {
  const params = useParams<{ tenantId: string }>()
  const router = useRouter()
  const tenantId = params.tenantId

  const { data, isLoading, isError, error, refetch } = useTenant(tenantId)
  const tenant = data?.data

  const suspendMutation = useSuspendTenant(tenantId)
  const reactivateMutation = useReactivateTenant(tenantId)

  async function handleSuspend() {
    try {
      await suspendMutation.mutateAsync()
      toast.success("Tenant suspended.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to suspend tenant.")
    }
  }

  async function handleReactivate() {
    try {
      await reactivateMutation.mutateAsync()
      toast.success("Tenant reactivated.")
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to reactivate tenant.")
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

  if (isError || !tenant) {
    return (
      <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">
          {error instanceof ApiError
            ? error.message
            : "Failed to load this tenant."}
        </p>
        <div className="mx-auto flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
          <Button variant="ghost" onClick={() => router.push("/tenants")}>
            Back to tenants
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
            <h1 className="text-xl font-semibold">{tenant.displayName}</h1>
            <TenantStatusBadge status={tenant.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            <Link href="/tenants" className="hover:underline">
              Tenants
            </Link>{" "}
            / {tenant.displayName}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            render={<Link href={`/tenants/${tenant.id}/edit`} />}
            nativeButton={false}
          >
            <PencilIcon />
            Edit
          </Button>

          {tenant.status === "active" ? (
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button variant="outline" disabled={suspendMutation.isPending}>
                    <PauseIcon />
                    Suspend
                  </Button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Suspend this tenant?</AlertDialogTitle>
                  <AlertDialogDescription>
                    {tenant.displayName} will lose access to the platform
                    until reactivated. This does not delete any data.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleSuspend}>
                    Suspend tenant
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}

          {tenant.status === "suspended" ? (
            <AlertDialog>
              <AlertDialogTrigger
                render={
                  <Button disabled={reactivateMutation.isPending}>
                    <PlayIcon />
                    Reactivate
                  </Button>
                }
              />
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Reactivate this tenant?</AlertDialogTitle>
                  <AlertDialogDescription>
                    {tenant.displayName} will regain access to the platform
                    immediately.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleReactivate}>
                    Reactivate tenant
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tenant details</CardTitle>
        </CardHeader>
        <CardContent className="divide-y">
          <DetailRow label="Tenant ID" value={<code className="text-xs">{tenant.id}</code>} />
          <DetailRow label="Legal name" value={tenant.legalName} />
          <DetailRow label="Display name" value={tenant.displayName} />
          <DetailRow label="Tier" value={tenant.tenantTier} />
          <DetailRow label="Default currency" value={tenant.defaultCurrencyCode} />
          <DetailRow
            label="Created"
            value={new Date(tenant.createdAt).toLocaleString()}
          />
          <DetailRow
            label="Metadata"
            value={
              Object.keys(tenant.metadata).length > 0 ? (
                <pre className="overflow-x-auto rounded-lg bg-muted p-3 text-xs">
                  {JSON.stringify(tenant.metadata, null, 2)}
                </pre>
              ) : (
                <span className="text-muted-foreground">None</span>
              )
            }
          />
        </CardContent>
      </Card>
    </div>
  )
}
