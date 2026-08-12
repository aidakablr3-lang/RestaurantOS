"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BoxIcon,
  LayersIcon,
  LayoutDashboardIcon,
  MenuIcon,
  PercentIcon,
  StoreIcon,
  TruckIcon,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLinkItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { usePermissionHelpers } from "@/hooks/use-permissions"
import { cn } from "@/lib/utils"

interface NavItem {
  label: string
  href: string
  icon: LucideIcon
  comingSoon?: boolean
  // UI visibility only -- hides a link the caller has no permission to act
  // on. The page itself (and, underneath that, the backend) is still the
  // real gate; a direct URL visit is handled by each page's own
  // usePermissionHelpers() check, not by this link being hidden.
  isVisible?: (perms: ReturnType<typeof usePermissionHelpers>) => boolean
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboardIcon },
  {
    label: "Restaurants",
    href: "/restaurants",
    icon: StoreIcon,
    isVisible: (perms) => perms.hasTenantWide("restaurant.read"),
  },
  {
    label: "Branches",
    href: "/branches",
    icon: StoreIcon,
    isVisible: (perms) => perms.hasAnywhere("branch.read"),
  },
  {
    label: "Modifiers",
    href: "/modifier-groups",
    icon: LayersIcon,
    isVisible: (perms) => perms.hasTenantWide("menu.read"),
  },
  {
    label: "Discounts",
    href: "/discounts",
    icon: PercentIcon,
    isVisible: (perms) => perms.hasTenantWide("billing.manage"),
  },
  {
    label: "Taxes",
    href: "/taxes",
    icon: PercentIcon,
    isVisible: (perms) => perms.hasTenantWide("billing.manage"),
  },
  {
    label: "Inventory categories",
    href: "/inventory-categories",
    icon: BoxIcon,
    isVisible: (perms) => perms.hasTenantWide("inventory.read"),
  },
  {
    label: "Suppliers",
    href: "/suppliers",
    icon: TruckIcon,
    isVisible: (perms) => perms.hasTenantWide("purchasing.read"),
  },
]

function useVisibleNavItems() {
  const perms = usePermissionHelpers()
  return NAV_ITEMS.filter((item) => perms.isLoading || !item.isVisible || item.isVisible(perms))
}

export function AppSidebar() {
  const pathname = usePathname()
  const items = useVisibleNavItems()

  return (
    <aside className="hidden w-56 shrink-0 border-r bg-sidebar text-sidebar-foreground md:flex md:flex-col">
      <div className="flex h-14 items-center border-b px-4">
        <Link href="/dashboard" className="text-sm font-semibold">
          RestaurantOS
        </Link>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {items.map((item) => {
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

// The sidebar is hidden below the `md` breakpoint (`AppSidebar`'s own
// `hidden md:flex`) -- without this, a phone-width user would have no way
// to navigate between Dashboard/Restaurants/Branches at all once past the
// first page. Reuses the same permission-filtered item list and the
// existing DropdownMenu primitive rather than a new mobile-nav mechanism.
export function MobileNav() {
  const items = useVisibleNavItems()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon" aria-label="Open navigation menu" className="md:hidden">
            <MenuIcon />
          </Button>
        }
      />
      <DropdownMenuContent align="start">
        {items.map((item) => {
          const Icon = item.icon
          if (item.comingSoon) {
            return (
              <DropdownMenuItem key={item.href} disabled>
                <Icon />
                {item.label}
                <Badge variant="outline" className="ml-auto text-[10px] text-muted-foreground">
                  Soon
                </Badge>
              </DropdownMenuItem>
            )
          }
          return (
            <DropdownMenuLinkItem key={item.href} render={<Link href={item.href} />}>
              <Icon />
              {item.label}
            </DropdownMenuLinkItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
