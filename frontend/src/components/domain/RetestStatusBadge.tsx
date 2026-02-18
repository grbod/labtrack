import { CheckCircle2, AlertTriangle, Clock } from "lucide-react"
import type { RetestStatus } from "@/types"

interface RetestStatusBadgeProps {
  status: RetestStatus
}

export function RetestStatusBadge({ status }: RetestStatusBadgeProps) {
  if (status === "completed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
        <CheckCircle2 className="h-3 w-3" />
        Completed
      </span>
    )
  }

  if (status === "review_required") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-700">
        <AlertTriangle className="h-3 w-3" />
        Review Required
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
      <Clock className="h-3 w-3" />
      Pending
    </span>
  )
}
