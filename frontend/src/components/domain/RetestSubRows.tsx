/**
 * Retest Sub-Rows Component
 *
 * Renders expandable sub-rows for lots with retest requests.
 * Each retest request gets its own row showing reference, tests, and status.
 */

import { Loader2, RefreshCw } from "lucide-react"
import { useRetestRequests } from "@/hooks/useRetests"
import { TableCell, TableRow } from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { formatDateWithRelative } from "@/lib/date-utils"
import { RetestStatusBadge } from "./RetestStatusBadge"
import type { RetestRequest } from "@/types"

interface RetestSubRowsProps {
  /** Lot ID to fetch retests for */
  lotId: number
  /** Number of columns in the parent table (for colspan) */
  colSpan: number
  /** Callback when a retest row is clicked */
  onRetestClick: () => void
}

export function RetestSubRows({ lotId, colSpan, onRetestClick }: RetestSubRowsProps) {
  const { data: retestData, isLoading } = useRetestRequests(lotId)
  const retestRequests = retestData?.items ?? []

  if (isLoading) {
    return (
      <TableRow className="bg-amber-50/30">
        <TableCell colSpan={colSpan} className="py-3">
          <div className="flex items-center gap-2 text-sm text-amber-600 pl-8">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading retests...
          </div>
        </TableCell>
      </TableRow>
    )
  }

  if (retestRequests.length === 0) {
    return null
  }

  return (
    <>
      {retestRequests.map((request) => (
        <RetestRow
          key={request.id}
          request={request}
          colSpan={colSpan}
          onClick={onRetestClick}
        />
      ))}
    </>
  )
}

interface RetestRowProps {
  request: RetestRequest
  colSpan: number
  onClick: () => void
}

function RetestRow({ request, colSpan, onClick }: RetestRowProps) {
  const testNames = request.items
    .map((item) => item.test_type)
    .filter(Boolean)
    .join(", ") || "—"

  const isPending = request.status === "pending"
  const isReviewRequired = request.status === "review_required"

  return (
    <TableRow
      onClick={onClick}
      className={cn(
        "cursor-pointer transition-colors",
        isPending && "bg-amber-50/50 hover:bg-amber-100/50",
        isReviewRequired && "bg-yellow-50/50 hover:bg-yellow-100/50",
        !isPending && !isReviewRequired && "bg-slate-50/50 hover:bg-slate-100/50"
      )}
    >
      <TableCell colSpan={colSpan} className="py-2">
        <div className="flex items-center gap-4 pl-8">
          {/* Indent indicator */}
          <div className="flex items-center gap-2 min-w-[140px]">
            <RefreshCw className="h-3.5 w-3.5 text-amber-500" />
            <span className="font-mono text-sm font-medium text-amber-800">
              {request.reference_number}
            </span>
          </div>

          {/* Test names */}
          <div className="flex-1 text-sm text-slate-600 truncate" title={testNames}>
            {testNames}
          </div>

          {/* Date */}
          <div className="text-xs text-slate-400 min-w-[80px] text-right">
            {formatDateWithRelative(request.created_at)}
          </div>

          {/* Status badge */}
          <RetestStatusBadge status={request.status} />
        </div>
      </TableCell>
    </TableRow>
  )
}

export default RetestSubRows
