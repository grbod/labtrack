import { useState } from "react"
import { format } from "date-fns"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Loader2, Download, ChevronDown, ChevronRight, History } from "lucide-react"
import { useLotAuditHistory } from "@/hooks/useAudit"
import type { AuditLogEntry, AuditAction } from "@/types"
import { cn } from "@/lib/utils"

interface AuditTrailModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  lotId: number
  referenceNumber: string
}

const ACTION_COLORS: Record<AuditAction, { bg: string; text: string; label: string }> = {
  insert: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Created" },
  update: { bg: "bg-blue-100", text: "text-blue-700", label: "Updated" },
  delete: { bg: "bg-red-100", text: "text-red-700", label: "Deleted" },
  approve: { bg: "bg-emerald-100", text: "text-emerald-700", label: "Approved" },
  reject: { bg: "bg-red-100", text: "text-red-700", label: "Rejected" },
  override: { bg: "bg-amber-100", text: "text-amber-700", label: "Override" },
}

const TABLE_LABELS: Record<string, string> = {
  lots: "Lot",
  test_results: "Test Result",
  coa_releases: "COA Release",
}

function formatFieldName(field: string): string {
  return field
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

interface AuditEntryProps {
  entry: AuditLogEntry
  isLast: boolean
}

function AuditEntry({ entry, isLast }: AuditEntryProps) {
  const [expanded, setExpanded] = useState(false)
  const actionConfig = ACTION_COLORS[entry.action] || ACTION_COLORS.update
  const tableLabel = TABLE_LABELS[entry.table_name] || entry.table_name
  const hasChanges = Object.keys(entry.changes || {}).length > 0

  return (
    <div className="relative pl-6">
      {/* Timeline line */}
      {!isLast && (
        <div className="absolute left-[9px] top-6 bottom-0 w-0.5 bg-slate-200" />
      )}

      {/* Timeline dot */}
      <div
        className={cn(
          "absolute left-0 top-1.5 h-[18px] w-[18px] rounded-full border-2 border-white shadow-sm",
          actionConfig.bg
        )}
      />

      {/* Entry content */}
      <div className="pb-4">
        <div
          className={cn(
            "flex items-start justify-between gap-2 rounded-lg p-3 transition-colors",
            hasChanges && "cursor-pointer hover:bg-slate-50"
          )}
          onClick={() => hasChanges && setExpanded(!expanded)}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={cn("text-[10px] px-1.5 py-0", actionConfig.bg, actionConfig.text)}>
                {actionConfig.label}
              </Badge>
              <span className="text-[12px] text-slate-500">{tableLabel}</span>
              {entry.reason && (
                <span className="text-[11px] text-slate-400 italic truncate max-w-[200px]">
                  "{entry.reason}"
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[13px] font-medium text-slate-700">
                {entry.username || "System"}
              </span>
              <span className="text-[12px] text-slate-400">
                {format(new Date(entry.timestamp), "MMM d, yyyy 'at' h:mm a")}
              </span>
            </div>
          </div>
          {hasChanges && (
            <button className="text-slate-400 hover:text-slate-600 p-1">
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          )}
        </div>

        {/* Expanded changes */}
        {expanded && hasChanges && (
          <div className="mt-2 ml-3 rounded-lg bg-slate-50 p-3 text-[12px]">
            <table className="w-full">
              <thead>
                <tr className="text-slate-500 text-left">
                  <th className="pb-2 font-medium">Field</th>
                  <th className="pb-2 font-medium">From</th>
                  <th className="pb-2 font-medium">To</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {Object.entries(entry.changes).map(([field, change]) => (
                  <tr key={field}>
                    <td className="py-1.5 pr-3 text-slate-600 font-medium">
                      {formatFieldName(field)}
                    </td>
                    <td className="py-1.5 pr-3 text-red-600 line-through">
                      {formatValue(change.from)}
                    </td>
                    <td className="py-1.5 text-emerald-600">
                      {formatValue(change.to)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export function AuditTrailModal({
  open,
  onOpenChange,
  lotId,
  referenceNumber,
}: AuditTrailModalProps) {
  const { data, isLoading } = useLotAuditHistory(lotId)

  const handleExportCSV = () => {
    if (!data?.items) return

    const headers = ["Timestamp", "Action", "Table", "User", "Changes", "Reason"]
    const rows = data.items.map((entry) => [
      format(new Date(entry.timestamp), "yyyy-MM-dd HH:mm:ss"),
      entry.action,
      entry.table_name,
      entry.username || "System",
      Object.entries(entry.changes || {})
        .map(([k, v]) => `${k}: ${formatValue(v.from)} → ${formatValue(v.to)}`)
        .join("; "),
      entry.reason || "",
    ])

    const csv = [headers.join(","), ...rows.map((r) => r.map((c) => `"${c}"`).join(","))].join("\n")

    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `audit-trail-${referenceNumber}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <History className="h-5 w-5 text-slate-600" />
            Audit Trail: {referenceNumber}
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : !data?.items || data.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-500">
            <History className="h-10 w-10 text-slate-300 mb-3" />
            <p className="text-[14px]">No audit history available</p>
          </div>
        ) : (
          <>
            {/* Summary bar */}
            <div className="flex items-center justify-between px-1 py-2 border-b border-slate-200">
              <div className="text-[13px] text-slate-500">
                {data.total} entries across{" "}
                {data.tables_included.map((t) => TABLE_LABELS[t] || t).join(", ")}
              </div>
              <Button variant="outline" size="sm" onClick={handleExportCSV}>
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Export CSV
              </Button>
            </div>

            {/* Timeline */}
            <div className="flex-1 overflow-y-auto py-4 -mr-2 pr-2">
              {data.items.map((entry, index) => (
                <AuditEntry
                  key={entry.id}
                  entry={entry}
                  isLast={index === data.items.length - 1}
                />
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
