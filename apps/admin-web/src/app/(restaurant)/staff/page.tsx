"use client"

import * as React from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { CheckIcon, CopyIcon, PlusIcon, UsersIcon } from "lucide-react"
import { toast } from "sonner"

import { PermissionRestricted } from "@/components/permission-restricted"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { EmptyState } from "@/components/ui/empty-state"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/ui/page-header"
import { Pagination } from "@/components/ui/pagination"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useBranches } from "@/hooks/use-branches"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { useAssignUserRole, useRoles } from "@/hooks/use-roles"
import { useCreateUser, useUsers } from "@/hooks/use-users"
import { ApiError } from "@/lib/api-client"
import { type AssignRoleFormValues, assignRoleSchema, type CreateUserFormValues, createUserSchema } from "@/lib/schemas/user"
import type { User } from "@/types/user"

const PAGE_SIZE = 20

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  invited: "Invited",
  deactivated: "Deactivated",
}

function NewCredentialsDialog({
  created,
  onClose,
}: {
  created: { email: string; password: string } | null
  onClose: () => void
}) {
  const [copied, setCopied] = React.useState(false)

  async function copyPassword() {
    await navigator.clipboard.writeText(created?.password ?? "")
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Dialog open={created !== null} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Staff account created</DialogTitle>
          <DialogDescription>
            Share this password with {created?.email} over a channel you trust. It is shown only
            once here and cannot be retrieved again -- if it&apos;s lost, you&apos;ll need to
            create a new account.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 rounded-lg border bg-muted/40 p-3">
          <code className="flex-1 overflow-x-auto text-sm">{created?.password}</code>
          <Button type="button" size="icon" variant="outline" onClick={copyPassword}>
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

function CreateStaffDialog({
  onCreated,
}: {
  onCreated: (created: { email: string; password: string }) => void
}) {
  const [open, setOpen] = React.useState(false)
  const createUser = useCreateUser()

  const defaults: CreateUserFormValues = { email: "", phone: "" }
  const form = useForm<CreateUserFormValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  async function onSubmit(values: CreateUserFormValues) {
    try {
      const result = await createUser.mutateAsync({
        email: values.email,
        phone: values.phone || undefined,
      })
      toast.success("Staff account created.")
      setOpen(false)
      if (result.data.generatedPassword) {
        onCreated({ email: values.email, password: result.data.generatedPassword })
      }
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create this account.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button size="sm">
            <PlusIcon />
            Add staff
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a staff account</DialogTitle>
          <DialogDescription>
            A password is generated automatically and shown once after creation. Grant a role
            afterward to give this account access.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" placeholder="waiter@example.com" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Phone (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="+91 90000 00000" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={createUser.isPending}>
                {createUser.isPending ? "Creating…" : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function GrantRoleDialog({ user }: { user: User }) {
  const [open, setOpen] = React.useState(false)
  const { data: rolesResult, isLoading: rolesLoading } = useRoles({ limit: 100 }, { enabled: open })
  const { data: branchesResult, isLoading: branchesLoading } = useBranches(
    { limit: 100 },
    { enabled: open }
  )
  const assignRole = useAssignUserRole()

  const defaults: AssignRoleFormValues = { roleId: "", branchId: "" }
  const form = useForm<AssignRoleFormValues>({
    resolver: zodResolver(assignRoleSchema),
    defaultValues: defaults,
  })

  function handleOpenChange(next: boolean) {
    if (next) form.reset(defaults)
    setOpen(next)
  }

  const roles = rolesResult?.data ?? []
  const branches = branchesResult?.data ?? []
  const selectedRole = roles.find((r) => r.id === form.watch("roleId"))

  async function onSubmit(values: AssignRoleFormValues) {
    try {
      await assignRole.mutateAsync({
        userId: user.id,
        roleId: values.roleId,
        branchId: values.branchId || null,
      })
      toast.success(`Role granted to ${user.email}.`)
      setOpen(false)
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to grant this role.")
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button size="sm" variant="outline">Grant role</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Grant a role to {user.email}</DialogTitle>
          <DialogDescription>
            Branch-scoped roles apply only at the selected branch. Leave the branch empty for a
            tenant-wide role.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4" noValidate>
            <FormField
              control={form.control}
              name="roleId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    items={Object.fromEntries(roles.map((role) => [role.id, role.name]))}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={rolesLoading ? "Loading roles…" : "Select a role"} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {roles.map((role) => (
                        <SelectItem key={role.id} value={role.id}>
                          {role.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            {selectedRole?.defaultScope === "branch" ? (
              <FormField
                control={form.control}
                name="branchId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Branch</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      items={Object.fromEntries(branches.map((branch) => [branch.id, branch.name]))}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue
                            placeholder={branchesLoading ? "Loading branches…" : "Select a branch"}
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {branches.map((branch) => (
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
            ) : null}
            <DialogFooter>
              <Button type="submit" disabled={assignRole.isPending}>
                {assignRole.isPending ? "Granting…" : "Grant role"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function StaffPage() {
  const [offset, setOffset] = React.useState(0)
  const [justCreated, setJustCreated] = React.useState<{ email: string; password: string } | null>(
    null
  )
  const perms = usePermissionHelpers()
  // Mirrors users_router.py's own gate exactly: POST/GET /api/v1/users
  // both require roles.assign at any scope -- a bare account is only
  // useful to whoever can follow up with a role grant.
  const canAccess = perms.hasAnywhere("roles.assign")

  const { data, isLoading, isError, error, refetch } = useUsers(
    { offset, limit: PAGE_SIZE },
    { enabled: !perms.isLoading && canAccess }
  )

  const users = data?.data ?? []
  const meta = data?.meta
  const loading = perms.isLoading || isLoading

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Staff"
        description="Create staff accounts and grant them roles. New accounts have no access until a role is granted."
        actions={canAccess ? <CreateStaffDialog onCreated={setJustCreated} /> : undefined}
      />

      {!perms.isLoading && !canAccess ? (
        <PermissionRestricted resource="staff" />
      ) : isError ? (
        <div className="grid gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Failed to load staff accounts."}
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
      ) : users.length === 0 ? (
        <EmptyState
          icon={UsersIcon}
          title="No staff accounts yet"
          description="Add a staff account, then grant it a role."
          action={<CreateStaffDialog onCreated={setJustCreated} />}
        />
      ) : (
        <div className="min-w-0 rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Phone</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-1">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.email}</TableCell>
                  <TableCell className="text-muted-foreground">{user.phone ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={user.status === "active" ? "secondary" : "outline"}>
                      {STATUS_LABEL[user.status] ?? user.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <GrantRoleDialog user={user} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {meta && meta.total > 0 ? (
        <Pagination offset={meta.offset} limit={meta.limit} total={meta.total} onOffsetChange={setOffset} />
      ) : null}

      <NewCredentialsDialog created={justCreated} onClose={() => setJustCreated(null)} />
    </div>
  )
}
