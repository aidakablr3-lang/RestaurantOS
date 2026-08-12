import { useAuthStore } from "@/stores/auth-store"

// There is no GET /me/profile endpoint on the backend (see auth-store.ts's
// own note) and no user-directory page anywhere in this app -- the only
// place the current user's id lives is the access token's own "sub"
// claim (JWTTokenService signs it as such; see
// modules/identity/infrastructure/security/jwt_token_service.py).
// Decoding it client-side is read-only and purely for pre-filling forms
// that need an "approving user" id (refunds, stock adjustments) with
// the person who's actually here doing the approving -- never used for
// an authorization decision, which the backend always re-derives from
// the token itself.
function decodeAccessTokenSubject(accessToken: string): string | null {
  try {
    const [, payload] = accessToken.split(".")
    if (!payload) return null
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
    const claims = JSON.parse(json) as { sub?: string }
    return claims.sub ?? null
  } catch {
    return null
  }
}

export function useCurrentUserId(): string | null {
  const accessToken = useAuthStore((state) => state.accessToken)
  if (!accessToken) return null
  return decodeAccessTokenSubject(accessToken)
}
