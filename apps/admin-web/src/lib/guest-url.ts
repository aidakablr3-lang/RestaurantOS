// The guest ordering page (app/(guest)/order/[token]/page.tsx) is part of
// this same Next.js app, not a separate guest-facing domain -- so whatever
// origin the admin is being viewed from is exactly the origin a scanned QR
// code should point back to. No NEXT_PUBLIC_* base URL to misconfigure.
export function guestOrderUrl(token: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : ""
  return `${origin}/order/${encodeURIComponent(token)}`
}
