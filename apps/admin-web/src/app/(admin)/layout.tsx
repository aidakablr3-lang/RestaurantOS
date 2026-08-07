"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { LogOut } from "lucide-react"

import { AuthGuard } from "@/components/auth-guard"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { useAuthStore } from "@/stores/auth-store"

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const clearSession = useAuthStore((state) => state.clearSession)

  function handleLogout() {
    clearSession()
    router.replace("/login")
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-background">
        <header className="border-b">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
            <Link href="/tenants" className="text-sm font-semibold">
              RestaurantOS <span className="text-muted-foreground">Admin</span>
            </Link>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Log out"
                onClick={handleLogout}
              >
                <LogOut className="size-4" />
              </Button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
          {children}
        </main>
      </div>
    </AuthGuard>
  )
}
