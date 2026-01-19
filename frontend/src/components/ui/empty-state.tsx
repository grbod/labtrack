import { ArrowRight, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface EmptyStateProps {
  /** Icon to display */
  icon: LucideIcon
  /** Main title (e.g., "No products found") */
  title: string
  /** Description text */
  description?: string
  /** Action button text */
  actionLabel?: string
  /** Action button click handler */
  onAction?: () => void
  /** Additional className for the container */
  className?: string
}

/**
 * Empty state component for when there's no data to display.
 * Shows an icon, title, optional description, and optional action button.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16", className)}>
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center">
        <Icon className="h-8 w-8 text-slate-400" />
      </div>
      <p className="mt-5 text-[15px] font-medium text-slate-600">{title}</p>
      {description && (
        <p className="mt-1 text-[14px] text-slate-500">{description}</p>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold text-blue-600 hover:text-blue-700 transition-colors"
        >
          {actionLabel}
          <ArrowRight className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
