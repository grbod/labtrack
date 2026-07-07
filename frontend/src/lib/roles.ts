import type { User, UserRole } from "@/types"

/**
 * True when `user` is signed in and holds one of `roles`. Server-side guards are
 * the real enforcement; this is for hiding dead-end UI (nav items, buttons) and
 * route redirects. A null/undefined user always fails.
 */
export function hasRole(user: User | null | undefined, ...roles: UserRole[]): boolean {
  return !!user && roles.includes(user.role)
}
