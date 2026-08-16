/**
 * Mirrors modules/identity/presentation/api/v1/users_router.py's
 * UserResponseSchema / CreateUserRequestSchema.
 *
 * ``generatedPassword`` is only ever present on the response to a
 * *create* call that didn't supply its own password, and only that
 * once -- the backend never stores or re-returns it (Argon2 hashing is
 * one-way). See CreateUserUseCase's own docstring.
 */

export type UserStatus = "invited" | "active" | "deactivated"

export interface User {
  id: string
  tenantId: string
  email: string | null
  phone: string | null
  status: UserStatus
  createdAt: string
  generatedPassword?: string | null
}

export interface CreateUserRequest {
  email: string
  phone?: string | null
  password?: string | null
}

export interface ListUsersParams {
  offset?: number
  limit?: number
}
