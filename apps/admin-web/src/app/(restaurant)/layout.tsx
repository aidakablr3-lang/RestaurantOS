"use client"

import { useRouter } from "next/navigation"
import { LogOutIcon } from "lucide-react"

import { AppSidebar } from "@/components/app-sidebar"
import { AuthGuard } from "@/components/auth-guard"
import { ThemeToggle } from "@/components/theme-toggle"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { logout as logoutRequest } from "@/lib/api/auth"
import { useAuthStore } from "@/stores/auth-store"

function initialsFor(email: string | null): string {
  if (!email) return "?"
  return email.slice(0, 2).toUpperCase()
}

export default function RestaurantAppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const email = useAuthStore((state) => state.email)
  const tenantId = useAuthStore((state) => state.tenantId)
  const refreshToken = useAuthStore((state) => state.refreshToken)
  const clearSession = useAuthStore((state) => state.clearSession)

  async function handleLogout() {
    if (tenantId && refreshToken) {
      // Best-effort -- the server-side session is revoked if this
      // succeeds, but the client must sign the user out either way (e.g.
      // if the network is down or the refresh token already expired).
      try {
        await logoutRequest({ tenantId, refreshToken })
      } catch {
        // ignored
      }
    }
    clearSession()
    router.replace("/login")
  }

  return (
    <AuthGuard>
      <div className="flex min-h-screen bg-background">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-14 items-center justify-between border-b px-4 sm:px-6">
            <div className="min-w-0">
              {tenantId && (
                <p className="truncate text-xs text-muted-foreground">
                  Tenant <span className="font-mono">{tenantId}</span>
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <Button variant="ghost" size="icon" aria-label="Account menu">
                      <Avatar className="size-7">
                        <AvatarFallback>{initialsFor(email)}</AvatarFallback>
                      </Avatar>
                    </Button>
                  }
                />
                <DropdownMenuContent>
                  <DropdownMenuLabel>{email ?? "Signed in"}</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive" onClick={handleLogout}>
                    <LogOutIcon />
                    Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>
          <main className="flex-1 px-4 py-6 sm:px-6">{children}</main>
        </div>
      </div>
    </AuthGuard>
  )
}
