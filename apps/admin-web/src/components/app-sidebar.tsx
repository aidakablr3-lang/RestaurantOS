"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  CalendarClockIcon,
  LayoutDashboardIcon,
  StoreIcon,
  UtensilsCrossedIcon,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface NavItem {
  label: string
  href: string
  icon: LucideIcon
  comingSoon?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboardIcon },
  { label: "Restaurants", href: "/restaurants", icon: StoreIcon },
  { label: "Branches", href: "/branches", icon: StoreIcon },
  { label: "Reservations", href: "/reservations", icon: CalendarClockIcon, comingSoon: true },
  { label: "Menu", href: "/menu", icon: UtensilsCrossedIcon, comingSoon: true },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden w-56 shrink-0 border-r bg-sidebar text-sidebar-foreground md:flex md:flex-col">
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/dashboard" className="text-sm font-semibold">
          RestaurantOS
        </Link>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
          const Icon = item.icon

          if (item.comingSoon) {
            return (
              <div
                key={item.href}
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground/60"
                aria-disabled="true"
              >
                <Icon className="size-4" />
                <span className="flex-1">{item.label}</span>
                <Badge variant="outline" className="text-[10px] text-muted-foreground">
                  Soon
                </Badge>
              </div>
            )
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                active && "bg-sidebar-accent text-sidebar-accent-foreground"
              )}
            >
              <Icon className="size-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
