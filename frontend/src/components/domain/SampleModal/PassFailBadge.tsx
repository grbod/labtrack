import { Check, X, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

interface PassFailBadgeProps {
  /** Pass/fail status: 'pass', 'fail', or null for no result */
  status: 'pass' | 'fail' | null
  /** Whether this test is flagged for QC review */
  isFlagged?: boolean
  /** Additional class names */
  className?: string
}

/**
 * Pass/Fail badge component for test results.
 * Shows green PASS, red FAIL with optional flagged indicator, or empty for no result.
 */
export function PassFailBadge({ status, isFlagged = false, className }: PassFailBadgeProps) {
  // No result yet - empty cell
  if (status === null) {
    return <span className={cn("text-slate-300", className)}>—</span>
  }

  // Pass
  if (status === 'pass') {
    return (
      <span className={cn("inline-flex items-center gap-1 text-emerald-600", className)}>
        <Check className="h-4 w-4" />
        <span className="text-xs font-medium">PASS</span>
      </span>
    )
  }

  // Fail
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span className="text-red-600 flex items-center gap-1">
        <X className="h-4 w-4" />
        <span className="text-xs font-medium">FAIL</span>
      </span>
      {isFlagged && (
        <span className="inline-flex items-center gap-0.5 ml-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700">
          <AlertTriangle className="h-3 w-3" />
          Flagged
        </span>
      )}
    </span>
  )
}
