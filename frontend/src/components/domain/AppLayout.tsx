import { Outlet, Navigate, Link } from "react-router-dom"
import { useAuthStore } from "@/store/auth"
import { Sidebar } from "./Sidebar"
import { Bell, HelpCircle, LogOut, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"

export function AppLayout() {
  const { isAuthenticated, user, logout } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header Bar */}
        <header className="flex h-14 items-center justify-between border-b border-slate-200/80 bg-white px-6 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-500 tracking-wide">Quality Assurance</span>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm" className="h-9 w-9 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100/80 rounded-lg transition-colors">
              <HelpCircle className="h-[18px] w-[18px]" />
            </Button>
            <Button variant="ghost" size="sm" className="h-9 w-9 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100/80 rounded-lg transition-colors relative">
              <Bell className="h-[18px] w-[18px]" />
            </Button>
            <Link to="/settings">
              <Button variant="ghost" size="sm" className="h-9 w-9 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100/80 rounded-lg transition-colors">
                <Settings className="h-[18px] w-[18px]" />
              </Button>
            </Link>
            <div className="mx-3 h-6 w-px bg-slate-200" />
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-slate-700 to-slate-900 text-sm font-semibold text-white ring-2 ring-white shadow-sm">
                {user?.username?.charAt(0).toUpperCase()}
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-semibold text-slate-900 leading-tight">{user?.username}</p>
                <p className="text-xs text-slate-500 capitalize leading-tight">{user?.role?.toLowerCase().replace('_', ' ')}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => logout()}
                className="ml-1 h-9 w-9 p-0 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              >
                <LogOut className="h-[18px] w-[18px]" />
              </Button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
