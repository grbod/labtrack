import { NavLink } from "react-router-dom"
import {
  LayoutDashboard,
  Package,
  FlaskConical,
  TestTube,
  FileInput,
  CheckSquare,
  FileText,
  ShieldCheck,
  Grid3x3,
} from "lucide-react"
import { cn } from "@/lib/utils"

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
      { label: "Dashboard", href: "/", icon: <LayoutDashboard className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Configuration",
    items: [
      { label: "Products", href: "/products", icon: <Package className="h-[18px] w-[18px]" /> },
      { label: "Lab Test Types", href: "/lab-tests", icon: <FlaskConical className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Sample Management",
    items: [
      { label: "Create Sample", href: "/samples", icon: <TestTube className="h-[18px] w-[18px]" /> },
      { label: "Import Results", href: "/import", icon: <FileInput className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Quality Control",
    items: [
      { label: "Approvals", href: "/approvals", icon: <CheckSquare className="h-[18px] w-[18px]" /> },
      { label: "Publish COA", href: "/publish", icon: <FileText className="h-[18px] w-[18px]" /> },
    ],
  },
  {
    title: "Development",
    items: [
      { label: "Grid Showcase", href: "/grid-showcase", icon: <Grid3x3 className="h-[18px] w-[18px]" /> },
    ],
  },
]

export function Sidebar() {
  return (
    <aside className="flex h-screen w-[240px] flex-col border-r border-slate-200/80 bg-white shadow-[1px_0_3px_0_rgba(0,0,0,0.02)]">
      {/* Logo */}
      <div className="flex h-14 items-center border-b border-slate-200/80 px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-slate-800 to-slate-900 shadow-sm">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <div className="ml-3">
          <span className="text-[15px] font-bold text-slate-900 tracking-tight">COA System</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-5">
        {navSections.map((section, idx) => (
          <div key={idx} className={cn(idx > 0 && "mt-7")}>
            {section.title && (
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
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-all duration-150",
                        isActive
                          ? "bg-slate-900 text-white shadow-sm"
                          : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
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

      {/* Footer */}
      <div className="border-t border-slate-200/80 px-5 py-4">
        <p className="text-[11px] font-medium text-slate-400 tracking-wide">
          Version 2.0.0
        </p>
      </div>
    </aside>
  )
}
