import { useState, useEffect, useMemo } from "react"
import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  Package,
  FlaskConical,
  TestTube,
  ShieldCheck,
  ClipboardList,
  FileCheck,
  Archive,
  Users,
  Settings,
  PanelLeftClose,
  PanelLeft,
  FolderArchive,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuthStore } from "@/store/auth"

const SIDEBAR_COLLAPSED_KEY = "sidebar-collapsed"

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
}

interface NavSection {
  title: string
  items: NavItem[]
  adminOnly?: boolean
}

const navSections: NavSection[] = [
  {
    title: "",
    items: [
      { label: "Dashboard", href: "/", icon: <LayoutDashboard className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Configuration",
    items: [
      { label: "Lab Test Types", href: "/lab-tests", icon: <FlaskConical className="h-[18px] w-[18px]" /> },
      { label: "Products", href: "/products", icon: <Package className="h-[18px] w-[18px]" /> },
      { label: "Customers", href: "/customers", icon: <Users className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Sample Management",
    items: [
      { label: "Create Sample", href: "/samples", icon: <TestTube className="h-[18px] w-[18px]" /> },
      { label: "Sample Tracker", href: "/tracker", icon: <ClipboardList className="h-[18px] w-[18px]" /> },
      { label: "Release Queue", href: "/release", icon: <FileCheck className="h-[18px] w-[18px]" /> },
      { label: "History", href: "/archive", icon: <Archive className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Admin",
    adminOnly: true,
    items: [
      { label: "Audit Trail", href: "/audittrail", icon: <FolderArchive className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Settings",
    items: [
      { label: "Settings", href: "/settings", icon: <Settings className="h-[18px] w-[18px]" /> },
    ],
  },
]

export function Sidebar() {
  const { user } = useAuthStore()
  const [isCollapsed, setIsCollapsed] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    return saved === "true"
  })

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isCollapsed))
  }, [isCollapsed])

  // Filter sections based on user role
  const isAdmin = user?.role === "admin" || user?.role === "qc_manager"
  const filteredSections = useMemo(() => {
    return navSections.filter((section) => !section.adminOnly || isAdmin)
  }, [isAdmin])

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r border-slate-200/80 bg-white shadow-[1px_0_3px_0_rgba(0,0,0,0.02)] transition-all duration-200",
        isCollapsed ? "w-[64px]" : "w-[240px]"
      )}
    >
      {/* Logo / Collapse Toggle */}
      <div className="flex h-14 items-center justify-between border-b border-slate-200/80 px-3">
        {isCollapsed ? (
          /* When collapsed: show expand button in place of logo */
          <button
            onClick={() => setIsCollapsed(false)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors mx-auto"
            title="Expand sidebar"
          >
            <PanelLeft className="h-5 w-5" />
          </button>
        ) : (
          /* When expanded: show logo + title + collapse button */
          <>
            <div className="flex items-center">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-slate-800 to-slate-900 shadow-sm shrink-0">
                <ShieldCheck className="h-5 w-5 text-white" />
              </div>
              <div className="ml-3">
                <span className="text-[15px] font-bold text-slate-900 tracking-tight">COA System</span>
              </div>
            </div>
            <button
              onClick={() => setIsCollapsed(true)}
              className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              title="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className={cn("flex-1 overflow-y-auto py-5", isCollapsed ? "px-2" : "px-3")}>
        {filteredSections.map((section, idx) => (
          <div key={idx} className={cn(idx > 0 && "mt-7")}>
            {section.title && !isCollapsed && (
              <div className="mb-2.5 px-3">
                <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">
                  {section.title}
                </span>
              </div>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.href}>
                  <NavLink
                    to={item.href}
                    end={item.href === "/"}
                    title={isCollapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center rounded-lg text-[13px] font-medium transition-all duration-150",
                        isCollapsed
                          ? "justify-center px-2 py-2.5"
                          : "gap-3 px-3 py-2.5",
                        isActive
                          ? "bg-slate-900 text-white shadow-sm"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      )
                    }
                  >
                    {item.icon}
                    {!isCollapsed && item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className={cn("border-t border-slate-200/80 py-4", isCollapsed ? "px-2" : "px-5")}>
        {!isCollapsed && (
          <p className="text-[11px] font-mono text-slate-400 tracking-wide">
            {__GIT_HASH__}
          </p>
        )}
      </div>
    </aside>
  )
}
