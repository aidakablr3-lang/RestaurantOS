"use client"

import * as React from "react"
import { useRouter } from "next/navigation"

import { useAuthStore } from "@/stores/auth-store"

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const accessToken = useAuthStore((state) => state.accessToken)
  const [hydrated, setHydrated] = React.useState(false)

  React.useEffect(() => {
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true)
    }
    return useAuthStore.persist.onFinishHydration(() => setHydrated(true))
  }, [])

  React.useEffect(() => {
    if (hydrated && !accessToken) {
      router.replace("/login")
    }
  }, [hydrated, accessToken, router])

  if (!hydrated || !accessToken) {
    return null
  }

  return <>{children}</>
}
