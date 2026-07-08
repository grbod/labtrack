import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAuthStore } from "@/store/auth"
import { hasRole } from "@/lib/roles"
import type { UserRole } from "@/types"

/**
 * Route guard that redirects to "/" when the signed-in user's role isn't in
 * `roles`. Thin client-side gate to keep users out of pages they can't use;
 * the API still enforces permissions on every request.
 */
export function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const user = useAuthStore((state) => state.user)
  if (!hasRole(user, ...roles)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
