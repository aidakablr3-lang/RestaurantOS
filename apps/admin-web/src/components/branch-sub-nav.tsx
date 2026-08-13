"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"

interface BranchSubNavProps {
  branchId: string
}

// A thin, route-backed sub-nav (not the Base UI Tabs primitive) so each
// section -- Overview / Dining Areas / Tables -- is a real, bookmarkable,
// back-button-friendly page, matching this app's existing convention of
// one route per concern (e.g. /branches/[id]/edit is its own route, not
// a tab). Operating Hours stays where Step 6.1 already built it, on the
// Overview page's own card+dialog -- relocating already-shipped, working
// UI into a new tab isn't warranted by this step's scope.
export function BranchSubNav({ branchId }: BranchSubNavProps) {
  const pathname = usePathname()

  const items = [
    { label: "Overview", href: `/branches/${branchId}` },
    { label: "Dining areas", href: `/branches/${branchId}/dining-areas` },
    { label: "Tables", href: `/branches/${branchId}/tables` },
    { label: "Reservations", href: `/branches/${branchId}/reservations` },
    { label: "Orders", href: `/branches/${branchId}/orders` },
    { label: "Kitchen", href: `/branches/${branchId}/kitchen` },
    { label: "Inventory", href: `/branches/${branchId}/inventory-items` },
    { label: "Purchase orders", href: `/branches/${branchId}/purchase-orders` },
    { label: "Cash drawer", href: `/branches/${branchId}/cash-drawer` },
    { label: "Reports", href: `/branches/${branchId}/reports` },
  ]

  return (
    <nav className="flex w-fit items-center gap-1 rounded-lg bg-muted p-1 text-sm">
      {items.map((item) => {
        const active =
          item.href === `/branches/${branchId}`
            ? pathname === item.href
            : pathname === item.href || pathname.startsWith(`${item.href}/`)
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-md px-3 py-1.5 font-medium text-muted-foreground transition-colors hover:text-foreground",
              active && "bg-background text-foreground shadow-sm"
            )}
          >
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}
