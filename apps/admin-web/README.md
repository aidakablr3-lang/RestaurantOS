# admin-web

Platform-admin frontend for RestaurantOS's Tenant Platform (Sprint 4.1). Next.js 15 (App Router) + React 19 + TypeScript + Tailwind + shadcn/ui + TanStack Query + Zustand + React Hook Form + Zod.

## Getting started

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). `NEXT_PUBLIC_API_BASE_URL` in `.env.local` must point at a running `services/api` instance (see the repo root `docs/AI_HANDOFF.md`).

## Scope

Tenant Administration: list, details, create, edit, suspend, reactivate. Subscription status, quota dashboard, feature-flag display, and tenant settings are deferred — the backend only exposes those as self-service endpoints scoped to the caller's own tenant (`/api/v1/tenants/me/*`), not to a platform admin viewing an arbitrary tenant. See `docs/AI_HANDOFF.md` for the tracked gap.
