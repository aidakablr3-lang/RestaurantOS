import { LockIcon } from "lucide-react"

import { EmptyState } from "@/components/ui/empty-state"

// UI-visibility only -- shown when usePermissionHelpers() says the caller
// lacks the permission a screen needs. The backend enforces the real
// boundary independently on every request; this is purely so a user
// without access sees an honest "you can't do this" state instead of a
// confusing 403 toast or an empty list that looks like "there's nothing
// here yet."
export function PermissionRestricted({ resource = "this page" }: { resource?: string }) {
  return (
    <EmptyState
      icon={LockIcon}
      title="You don't have access"
      description={`You don't have permission to view ${resource}. Ask an owner or manager if you think this is a mistake.`}
    />
  )
}
