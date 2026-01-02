import { Outlet, Navigate } from "react-router-dom"
import { useAuthStore } from "@/store/auth"
import { Sidebar } from "./Sidebar"

export function AppLayout() {
  const { isAuthenticated } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-muted/40 p-6">
        <Outlet />
      </main>
    </div>
  )
}
