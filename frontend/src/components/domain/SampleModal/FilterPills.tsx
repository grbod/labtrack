import { cn } from "@/lib/utils"
import type { TestFilterStatus } from "@/types"

interface FilterCounts {
  all: number
  pending: number
  passed: number
  failed: number
}

interface FilterPillsProps {
  /** Current filter status */
  filter: TestFilterStatus
  /** Counts for each filter category */
  counts: FilterCounts
  /** Callback when filter changes */
  onChange: (filter: TestFilterStatus) => void
  /** Additional class names */
  className?: string
}

const FILTERS: { key: TestFilterStatus; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'passed', label: 'Passed' },
  { key: 'failed', label: 'Failed' },
]

/**
 * Filter pills for test results table.
 * Shows All | Pending | Passed | Failed with counts.
 */
export function FilterPills({ filter, counts, onChange, className }: FilterPillsProps) {
  return (
    <div className={cn("flex items-center gap-1", className)}>
      {FILTERS.map(({ key, label }) => {
        const count = counts[key]
        const isActive = filter === key

        return (
          <button
            key={key}
            onClick={() => onChange(key)}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
              isActive
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            )}
          >
            {label}
            <span
              className={cn(
                "inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-xs",
                isActive
                  ? "bg-white/20 text-white"
                  : "bg-slate-200 text-slate-500"
              )}
            >
              {count}
            </span>
          </button>
        )
      })}
    </div>
  )
}
