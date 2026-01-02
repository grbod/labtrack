import { NavLink, useNavigate } from "react-router-dom"
import {
  LayoutDashboard,
  Package,
  FlaskConical,
  TestTube,
  FileInput,
  CheckSquare,
  FileText,
  LogOut,
  ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuthStore } from "@/store/auth"
import { Button } from "@/components/ui/button"

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
}

interface NavSection {
  title: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    title: "",
    items: [
      { label: "Dashboard", href: "/", icon: <LayoutDashboard className="h-4 w-4" /> },
    ],
  },
  {
    title: "Act I: Setup",
    items: [
      { label: "Products", href: "/products", icon: <Package className="h-4 w-4" /> },
      { label: "Lab Test Types", href: "/lab-tests", icon: <FlaskConical className="h-4 w-4" /> },
    ],
  },
  {
    title: "Act II: Samples",
    items: [
      { label: "Create Sample", href: "/samples", icon: <TestTube className="h-4 w-4" /> },
      { label: "Import Results", href: "/import", icon: <FileInput className="h-4 w-4" /> },
    ],
  },
  {
    title: "Act III: Finalize",
    items: [
      { label: "Approvals", href: "/approvals", icon: <CheckSquare className="h-4 w-4" /> },
      { label: "Publish", href: "/publish", icon: <FileText className="h-4 w-4" /> },
    ],
  },
]

export function Sidebar() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = async () => {
    await logout()
    navigate("/login")
  }

  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4">
        <FlaskConical className="mr-2 h-5 w-5 text-primary" />
        <span className="font-semibold text-sm">COA Manager</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-2">
        {navSections.map((section, idx) => (
          <div key={idx} className="mb-4">
            {section.title && (
              <div className="mb-1 flex items-center px-2 py-1">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {section.title}
                </span>
                <ChevronDown className="ml-auto h-3 w-3 text-muted-foreground" />
              </div>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.href}>
                  <NavLink
                    to={item.href}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )
                    }
                  >
                    {item.icon}
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* User section */}
      <div className="border-t p-2">
        <div className="flex items-center gap-2 rounded-md px-2 py-1.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
            {user?.username?.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium">{user?.username}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.role}</p>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleLogout}
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  )
}
