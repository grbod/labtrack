import { CornerUpLeft, PencilLine } from "lucide-react"
import { formatDateTime } from "@/lib/date-utils"
import type { ReviewThreadEvent } from "@/types"

interface ReviewThreadProps {
  events: ReviewThreadEvent[]
  className?: string
}

function formatRole(role: string | null): string {
  if (!role) return ""
  switch (role) {
    case "admin": return "Admin"
    case "qc_manager": return "QC Manager"
    case "lab_tech": return "Lab Tech"
    case "read_only": return "Read Only"
    default: return role
  }
}

export function ReviewThread({ events, className }: ReviewThreadProps) {
  if (!events || events.length === 0) return null

  return (
    <div className={className}>
      <div className="space-y-2">
        {events.map((event, index) => {
          const isReturn = event.type === "return"
          const authorDisplay = event.author ?? "Unknown"
          const roleDisplay = event.author_role ? ` (${formatRole(event.author_role)})` : ""

          return (
            <div
              key={index}
              className={
                isReturn
                  ? "flex gap-3 pl-3 border-l-2 border-amber-400"
                  : "flex gap-3 pl-3 border-l-2 border-slate-300"
              }
            >
              {/* Icon */}
              <div className="shrink-0 mt-0.5">
                {isReturn ? (
                  <CornerUpLeft className="h-3.5 w-3.5 text-amber-600" />
                ) : (
                  <PencilLine className="h-3.5 w-3.5 text-slate-500" />
                )}
              </div>

              {/* Content */}
              <div className="min-w-0 flex-1">
                <p className={`text-[11px] font-medium leading-tight ${isReturn ? "text-amber-700" : "text-slate-500"}`}>
                  {isReturn ? "Returned" : "Resolved"}&nbsp;&middot;&nbsp;
                  {authorDisplay}{roleDisplay}&nbsp;&middot;&nbsp;
                  {formatDateTime(event.at)}
                </p>
                <p className={`mt-0.5 text-[12px] whitespace-pre-wrap ${isReturn ? "text-amber-800" : "text-slate-600"}`}>
                  {event.message}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
