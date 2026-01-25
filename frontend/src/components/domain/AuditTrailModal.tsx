/**
 * Audit Trail Modal
 *
 * Displays the audit history for a specific record in a table format with:
 * - Flattened rows showing one row per field change
 * - Test result changes aggregated into lot's audit trail with context
 * - Annotations (comments and attachments) via popover
 * - Export functionality (CSV/PDF)
 *
 * Access: QC Manager and Admin only
 */

import { useState, useCallback, useRef, useMemo } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Loader2,
  MessageSquare,
  Paperclip,
  Download,
  FileText,
  AlertTriangle,
  Clock,
  Plus,
  Upload,
  FileSpreadsheet,
  Layers,
  List,
} from "lucide-react"
import { toast } from "sonner"

import {
  useAuditTrail,
  useAnnotations,
  useAddCommentAnnotation,
  useAddAttachmentAnnotation,
  useDownloadAttachment,
  useExportAuditCsv,
  useExportAuditPdf,
} from "@/hooks/useAudit"
import { useAuthStore } from "@/store/auth"
import type {
  AuditEntryDisplay,
  AuditAnnotation,
  AuditViewMode,
  ConsolidatedRow,
} from "@/api/audit"

interface AuditTrailModalProps {
  /** Table name for the record (e.g., "test_results", "lots") */
  tableName: string
  /** Record ID to show audit trail for */
  recordId: number
  /** Display title for the modal */
  title?: string
  /** Whether the modal is open */
  isOpen: boolean
  /** Callback when the modal should close */
  onClose: () => void
  /** Brand name for export filename (optional) */
  brand?: string
  /** Product name for export filename (optional) */
  productName?: string
  /** Lot number for export filename (optional) */
  lotNumber?: string
}

/** Flattened row data for the table */
interface FlattenedRow {
  id: string // unique key for React
  auditId: number
  timestamp: Date
  timestampDisplay: string
  username: string
  action: string
  actionDisplay: string
  field: string
  oldValue: string
  newValue: string
  reason: string | null
  annotationCount: number
}

/**
 * Get badge variant for action type
 */
function getActionBadgeVariant(
  action: string,
  field?: string
): "emerald" | "blue" | "amber" | "red" | "slate" | "violet" | "cyan" {
  // Status field changes get distinct styling (violet)
  if (action === "update" && field?.toLowerCase().includes("status")) {
    return "violet"
  }

  switch (action) {
    case "insert":
      return "emerald"    // Green for Created
    case "update":
      return "blue"       // Blue for Updated
    case "approve":
      return "cyan"       // Cyan for Approved (distinguish from Created)
    case "reject":
      return "red"
    case "delete":
      return "red"
    case "validation_failed":
      return "amber"
    default:
      return "slate"
  }
}

/**
 * Get display text for action badges
 * Status field changes show as "Status Change" instead of "Updated"
 */
function getActionDisplayText(
  action: string,
  actionDisplay: string,
  field?: string
): string {
  // Status field changes show as "Status Change"
  if (action === "update" && field?.toLowerCase().includes("status")) {
    return "Status Change"
  }
  return actionDisplay
}

/**
 * Format a value for display
 */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return ""
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No"
  }
  if (typeof value === "object") {
    return JSON.stringify(value)
  }
  return String(value)
}

/**
 * Format timestamp for table display (compact 24-hour format)
 */
function formatTableTimestamp(date: Date): string {
  const month = date.getMonth() + 1
  const day = date.getDate()
  const year = date.getFullYear().toString().slice(-2)
  const hours = date.getHours().toString().padStart(2, "0")
  const minutes = date.getMinutes().toString().padStart(2, "0")
  return `${month}/${day}/${year} ${hours}:${minutes}`
}

/**
 * Format file size for display
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Flatten audit entries into table rows (one per field change)
 */
function flattenEntries(entries: AuditEntryDisplay[]): FlattenedRow[] {
  const rows: FlattenedRow[] = []

  for (const entry of entries) {
    const timestamp = new Date(entry.timestamp)
    const timestampDisplay = formatTableTimestamp(timestamp)

    // If entry has changes, create a row for each change
    if (entry.changes && entry.changes.length > 0) {
      for (let i = 0; i < entry.changes.length; i++) {
        const change = entry.changes[i]
        rows.push({
          id: `${entry.id}-${i}`,
          auditId: entry.id,
          timestamp,
          timestampDisplay,
          username: entry.username,
          action: entry.action,
          actionDisplay: entry.action_display,
          field: change.field,
          oldValue: change.display_old ?? formatValue(change.old_value),
          newValue: change.display_new ?? formatValue(change.new_value),
          reason: i === 0 ? entry.reason : null, // Only show reason on first row
          annotationCount: i === 0 ? entry.annotation_count : -1, // -1 means don't show
        })
      }
    } else {
      // No changes - show the action without field details
      rows.push({
        id: `${entry.id}-0`,
        auditId: entry.id,
        timestamp,
        timestampDisplay,
        username: entry.username,
        action: entry.action,
        actionDisplay: entry.action_display,
        field: entry.is_bulk_operation && entry.bulk_summary ? entry.bulk_summary : "(record created)",
        oldValue: "",
        newValue: "",
        reason: entry.reason,
        annotationCount: entry.annotation_count,
      })
    }
  }

  return rows
}

/** Time window for collapsing rapid changes (5 seconds) */
const CONSOLIDATION_WINDOW_MS = 5000

/**
 * Extract test name from a prefixed field (e.g., "E. coli › Result Value" -> "E. coli")
 */
function extractTestName(field: string): string | null {
  const separator = " › "
  if (field.includes(separator)) {
    return field.split(separator)[0]
  }
  return null
}

/**
 * Extract test name from reason string (e.g., "Test result created: E. coli" -> "E. coli")
 */
function extractTestNameFromReason(reason: string | null): string | null {
  if (!reason) return null
  // Match patterns like "Test result created: E. coli" or "Test result update: Salmonella"
  // Use non-greedy match and trim result to handle trailing whitespace
  const match = reason.match(/Test result (?:created|update|updated):\s*(.+)/i)
  return match ? match[1].trim() : null
}

/**
 * Format a test result creation for summary view (field + newValue)
 */
function formatTestResultForSummary(
  changes: Array<{ field: string; newValue: string }>,
  reason: string | null
): { field: string; newValue: string } {
  const values: { [key: string]: string } = {}
  let testName = ""

  for (const change of changes) {
    const testNameFromField = extractTestName(change.field)
    if (testNameFromField) {
      testName = testNameFromField
    }
    // Normalize field name for matching (handle snake_case and spaces)
    const lowerField = change.field.toLowerCase().replace(/_/g, " ")
    if (lowerField.includes("test type") || lowerField === "test type") {
      values.testType = change.newValue
    } else if (lowerField.includes("result") && (lowerField.includes("value") || lowerField.includes("val"))) {
      values.resultValue = change.newValue
    } else if (lowerField.includes("unit")) {
      values.unit = change.newValue
    } else if (lowerField.includes("method")) {
      values.method = change.newValue
    }
  }

  // Use test name from field prefix, fall back to test_type value, then reason, then default
  // Ensure displayName is never empty (trim whitespace and provide fallback)
  const fromReason = extractTestNameFromReason(reason)
  const rawDisplayName = testName || values.testType || fromReason || ""
  const displayName = rawDisplayName.trim() || "Test"
  const fieldCount = changes.length

  // Build the new value string
  const newValueParts: string[] = []
  if (values.resultValue) {
    newValueParts.push(values.resultValue)
    if (values.unit) {
      newValueParts.push(` ${values.unit}`)
    }
  }
  if (values.method) {
    newValueParts.push(` (${values.method})`)
  }

  return {
    field: `${displayName} (${fieldCount} fields)`,
    newValue: newValueParts.join("") || "(created)",
  }
}

/**
 * Consolidate entries for summary view
 * - Groups CREATE actions for test results into single summary rows
 * - Collapses rapid changes within 5-second window
 * - Filters out no-op changes
 * - Shows status changes as distinct rows
 */
function consolidateEntries(entries: AuditEntryDisplay[]): ConsolidatedRow[] {
  const rows: ConsolidatedRow[] = []

  // Group entries by timestamp window and action type
  let i = 0
  while (i < entries.length) {
    const entry = entries[i]
    const timestamp = new Date(entry.timestamp)
    const timestampDisplay = formatTableTimestamp(timestamp)

    // For INSERT actions, consolidate into a summary
    if (entry.action === "insert") {
      // Handle INSERT with no changes (edge case)
      if (!entry.changes || entry.changes.length === 0) {
        rows.push({
          id: `consolidated-${entry.id}`,
          auditIds: [entry.id],
          primaryAuditId: entry.id,
          timestamp,
          timestampDisplay,
          username: entry.username,
          action: entry.action,
          actionDisplay: entry.action_display,
          field: "Record created",
          oldValue: "—",
          newValue: "—",
          reason: entry.reason,
          annotationCount: entry.annotation_count,
          consolidatedCount: 1,
        })
        i++
        continue
      }

      if (entry.changes.length > 0) {
      // Check if this looks like a test result creation
      const hasTestFields = entry.changes.some(
        (c) =>
          c.field.toLowerCase().includes("test type") ||
          c.field.toLowerCase().includes("result") ||
          c.field.toLowerCase().includes("method")
      )

      if (hasTestFields) {
        // Format as test result summary
        const changeData = entry.changes.map((c) => ({
          field: c.field,
          newValue: c.display_new ?? formatValue(c.new_value),
        }))
        const { field, newValue } = formatTestResultForSummary(changeData, entry.reason)

        rows.push({
          id: `consolidated-${entry.id}`,
          auditIds: [entry.id],
          primaryAuditId: entry.id,
          timestamp,
          timestampDisplay,
          username: entry.username,
          action: entry.action,
          actionDisplay: entry.action_display,
          field,
          oldValue: "—",
          newValue,
          reason: entry.reason,
          annotationCount: entry.annotation_count,
          consolidatedCount: entry.changes.length,
        })
        i++
        continue
      } else {
        // Non-test INSERT: show first meaningful field or count of fields created
        const firstChange = entry.changes[0]
        const firstVal = firstChange.display_new ?? formatValue(firstChange.new_value)
        const fieldLabel = entry.changes.length === 1
          ? firstChange.field
          : `${entry.changes.length} fields initialized`

        rows.push({
          id: `consolidated-${entry.id}`,
          auditIds: [entry.id],
          primaryAuditId: entry.id,
          timestamp,
          timestampDisplay,
          username: entry.username,
          action: entry.action,
          actionDisplay: entry.action_display,
          field: fieldLabel,
          oldValue: "—",
          newValue: entry.changes.length === 1 ? firstVal : "—",
          reason: entry.reason,
          annotationCount: entry.annotation_count,
          consolidatedCount: entry.changes.length,
        })
        i++
        continue
      }
      }
    }

    // For UPDATE actions, check for rapid changes to consolidate
    if (entry.action === "update") {
      const consolidatedAuditIds: number[] = [entry.id]
      let totalAnnotations = entry.annotation_count
      const allChanges: Array<{
        field: string
        oldValue: string
        newValue: string
      }> = []

      // Add changes from current entry, filtering out no-ops
      if (entry.changes) {
        for (const change of entry.changes) {
          const oldVal = change.display_old ?? formatValue(change.old_value)
          const newVal = change.display_new ?? formatValue(change.new_value)
          // Filter out no-op changes (same value or both empty)
          if (oldVal !== newVal) {
            allChanges.push({
              field: change.field,
              oldValue: oldVal,
              newValue: newVal,
            })
          }
        }
      }

      // Look ahead for entries within the consolidation window
      let j = i + 1
      while (j < entries.length) {
        const nextEntry = entries[j]
        const nextTimestamp = new Date(nextEntry.timestamp)
        const timeDiff = Math.abs(timestamp.getTime() - nextTimestamp.getTime())

        if (
          timeDiff <= CONSOLIDATION_WINDOW_MS &&
          nextEntry.action === "update" &&
          nextEntry.username === entry.username
        ) {
          consolidatedAuditIds.push(nextEntry.id)
          totalAnnotations += nextEntry.annotation_count

          if (nextEntry.changes) {
            for (const change of nextEntry.changes) {
              const oldVal = change.display_old ?? formatValue(change.old_value)
              const newVal = change.display_new ?? formatValue(change.new_value)
              // Filter out no-op changes (same value or both empty)
              if (oldVal !== newVal) {
                // Check if we already have a change for this field
                const existingIdx = allChanges.findIndex(
                  (c) => c.field === change.field
                )
                if (existingIdx >= 0) {
                  // Update to use latest new value
                  allChanges[existingIdx].newValue = newVal
                } else {
                  allChanges.push({
                    field: change.field,
                    oldValue: oldVal,
                    newValue: newVal,
                  })
                }
              }
            }
          }
          j++
        } else {
          break
        }
      }

      // Filter out status-only changes for separate handling
      const statusChanges = allChanges.filter((c) =>
        c.field.toLowerCase().includes("status")
      )
      const nonStatusChanges = allChanges.filter(
        (c) => !c.field.toLowerCase().includes("status")
      )

      // Create rows for non-status changes
      if (nonStatusChanges.length > 0) {
        for (const change of nonStatusChanges) {
          rows.push({
            id: `consolidated-${entry.id}-${change.field}`,
            auditIds: consolidatedAuditIds,
            primaryAuditId: entry.id,
            timestamp,
            timestampDisplay,
            username: entry.username,
            action: entry.action,
            actionDisplay: entry.action_display,
            field: change.field,
            oldValue: change.oldValue || "—",
            newValue: change.newValue || "—",
            reason: entry.reason,
            annotationCount:
              nonStatusChanges.indexOf(change) === 0 ? totalAnnotations : 0,
            consolidatedCount: consolidatedAuditIds.length,
          })
        }
      }

      // Create separate rows for status changes (important milestones)
      for (const change of statusChanges) {
        rows.push({
          id: `consolidated-${entry.id}-status-${change.field}`,
          auditIds: consolidatedAuditIds,
          primaryAuditId: entry.id,
          timestamp,
          timestampDisplay,
          username: entry.username,
          action: entry.action,
          actionDisplay: entry.action_display,
          field: change.field,
          oldValue: change.oldValue || "—",
          newValue: change.newValue || "—",
          reason: entry.reason,
          annotationCount: nonStatusChanges.length === 0 ? totalAnnotations : 0,
          consolidatedCount: 1, // Status changes shown individually
        })
      }

      // Edge case: UPDATE with all no-op changes still needs a row for visibility
      if (nonStatusChanges.length === 0 && statusChanges.length === 0) {
        rows.push({
          id: `consolidated-${entry.id}-noop`,
          auditIds: consolidatedAuditIds,
          primaryAuditId: entry.id,
          timestamp,
          timestampDisplay,
          username: entry.username,
          action: entry.action,
          actionDisplay: entry.action_display,
          field: "(no effective changes)",
          oldValue: "—",
          newValue: "—",
          reason: entry.reason,
          annotationCount: totalAnnotations,
          consolidatedCount: consolidatedAuditIds.length,
        })
      }

      // Skip the entries we consolidated
      i = j
      continue
    }

    // For other actions (approve, reject, delete, etc.), show as-is
    let field: string
    let oldValue = "—"
    let newValue = "—"

    if (entry.is_bulk_operation && entry.bulk_summary) {
      field = entry.bulk_summary
    } else if (entry.changes && entry.changes.length > 0) {
      const change = entry.changes[0]
      field = change.field
      oldValue = (change.display_old ?? formatValue(change.old_value)) || "—"
      newValue = (change.display_new ?? formatValue(change.new_value)) || "—"
    } else {
      // Use action-specific labels for better clarity
      switch (entry.action) {
        case "approve":
          field = "Record approved"
          break
        case "reject":
          field = "Record rejected"
          break
        case "delete":
          field = "Record deleted"
          break
        default:
          field = entry.action_display || "(record action)"
      }
    }

    rows.push({
      id: `consolidated-${entry.id}`,
      auditIds: [entry.id],
      primaryAuditId: entry.id,
      timestamp,
      timestampDisplay,
      username: entry.username,
      action: entry.action,
      actionDisplay: entry.action_display,
      field,
      oldValue,
      newValue,
      reason: entry.reason,
      annotationCount: entry.annotation_count,
      consolidatedCount: 1,
    })
    i++
  }

  return rows
}

/**
 * Annotation Item Component
 */
function AnnotationItem({
  annotation,
  auditId,
}: {
  annotation: AuditAnnotation
  auditId: number
}) {
  const downloadMutation = useDownloadAttachment()

  const handleDownload = useCallback(() => {
    if (!annotation.attachment_filename) return
    downloadMutation.mutate({
      auditId,
      annotationId: annotation.id,
      filename: annotation.attachment_filename,
    })
  }, [auditId, annotation, downloadMutation])

  return (
    <div className="flex items-start gap-2 py-2 border-b border-slate-100 last:border-b-0">
      {annotation.attachment_filename ? (
        <Paperclip className="h-3.5 w-3.5 text-slate-400 mt-0.5 flex-shrink-0" />
      ) : (
        <MessageSquare className="h-3.5 w-3.5 text-slate-400 mt-0.5 flex-shrink-0" />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-0.5">
          <span className="font-medium">{annotation.username || "Unknown"}</span>
          <span>•</span>
          <span>
            {new Date(annotation.created_at).toLocaleString("en-US", {
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}
          </span>
        </div>
        {annotation.comment && (
          <p className="text-sm text-slate-700">{annotation.comment}</p>
        )}
        {annotation.attachment_filename && (
          <button
            onClick={handleDownload}
            disabled={downloadMutation.isPending}
            className="mt-1 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 hover:underline"
          >
            <FileText className="h-3 w-3" />
            {annotation.attachment_filename}
            {annotation.attachment_size && (
              <span className="text-slate-400">
                ({formatFileSize(annotation.attachment_size)})
              </span>
            )}
            {downloadMutation.isPending && (
              <Loader2 className="h-3 w-3 animate-spin" />
            )}
          </button>
        )}
      </div>
    </div>
  )
}

/**
 * Annotation Popover Component
 */
function AnnotationPopover({
  auditId,
  annotationCount,
}: {
  auditId: number
  annotationCount: number
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [showAddComment, setShowAddComment] = useState(false)
  const [comment, setComment] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: annotationsData, isLoading } = useAnnotations(auditId, isOpen)
  const addCommentMutation = useAddCommentAnnotation()
  const addAttachmentMutation = useAddAttachmentAnnotation()

  const handleAddComment = useCallback(async () => {
    if (!comment.trim()) return
    try {
      await addCommentMutation.mutateAsync({ auditId, comment: comment.trim() })
      setComment("")
      setShowAddComment(false)
      toast.success("Comment added")
    } catch {
      toast.error("Failed to add comment")
    }
  }, [auditId, comment, addCommentMutation])

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return

      if (file.size > 10 * 1024 * 1024) {
        toast.error("File size must be less than 10MB")
        return
      }

      try {
        await addAttachmentMutation.mutateAsync({ auditId, file })
        toast.success("Attachment added")
      } catch {
        toast.error("Failed to add attachment")
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = ""
        }
      }
    },
    [auditId, addAttachmentMutation]
  )

  const annotations = annotationsData?.items || []

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button
          className="inline-flex items-center justify-center h-7 min-w-[36px] px-1.5 text-xs rounded hover:bg-slate-100 transition-colors"
        >
          {annotationCount > 0 ? (
            <span className="flex items-center gap-1 text-blue-600 font-medium">
              <MessageSquare className="h-3.5 w-3.5" />
              {annotationCount}
            </span>
          ) : (
            <Plus className="h-3.5 w-3.5 text-slate-400" />
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="p-3 border-b border-slate-100">
          <h4 className="text-sm font-medium text-slate-900">Annotations</h4>
        </div>

        <div className="max-h-60 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            </div>
          ) : annotations.length > 0 ? (
            <div className="px-3 py-2">
              {annotations.map((annotation) => (
                <AnnotationItem
                  key={annotation.id}
                  annotation={annotation}
                  auditId={auditId}
                />
              ))}
            </div>
          ) : (
            <div className="px-3 py-4 text-center text-sm text-slate-500">
              No annotations yet
            </div>
          )}
        </div>

        <div className="p-3 border-t border-slate-100 bg-slate-50/50">
          {showAddComment ? (
            <div className="space-y-2">
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add a comment..."
                className="min-h-[60px] text-sm resize-none"
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowAddComment(false)
                    setComment("")
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleAddComment}
                  disabled={!comment.trim() || addCommentMutation.isPending}
                >
                  {addCommentMutation.isPending && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                  )}
                  Add
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs"
                onClick={() => setShowAddComment(true)}
              >
                <MessageSquare className="h-3.5 w-3.5 mr-1" />
                Comment
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1 text-xs"
                onClick={() => fileInputRef.current?.click()}
                disabled={addAttachmentMutation.isPending}
              >
                {addAttachmentMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                ) : (
                  <Upload className="h-3.5 w-3.5 mr-1" />
                )}
                Attach
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

/**
 * Main Audit Trail Modal Component
 */
export function AuditTrailModal({
  tableName,
  recordId,
  title,
  isOpen,
  onClose,
  brand,
  productName,
  lotNumber,
}: AuditTrailModalProps) {
  const { user } = useAuthStore()
  const exportCsvMutation = useExportAuditCsv()
  const exportPdfMutation = useExportAuditPdf()

  // View mode state - default to summary
  const [viewMode, setViewMode] = useState<AuditViewMode>("summary")

  // Check access - QC Manager or Admin only
  const hasAccess = user?.role === "qc_manager" || user?.role === "admin"

  // Fetch audit trail
  const { data: auditData, isLoading, error } = useAuditTrail(
    tableName,
    recordId,
    isOpen && hasAccess
  )

  // Flatten entries into rows (for detailed view)
  const detailedRows = useMemo(() => {
    if (!auditData?.entries) return []
    const rows = flattenEntries(auditData.entries)

    // Sort rows to keep related changes adjacent
    rows.sort((a, b) => {
      // Primary: timestamp descending (newest first)
      const timeDiff = b.timestamp.getTime() - a.timestamp.getTime()
      if (Math.abs(timeDiff) > 5000) return timeDiff // >5 seconds apart, use timestamp

      // Secondary: group by field prefix (test name like "Lead", "E. coli")
      const prefixA = a.field.split(" › ")[0] || a.field
      const prefixB = b.field.split(" › ")[0] || b.field
      if (prefixA !== prefixB) return prefixA.localeCompare(prefixB)

      // Tertiary: status changes go last within group
      const isStatusA = a.field.toLowerCase().includes("status")
      const isStatusB = b.field.toLowerCase().includes("status")
      if (isStatusA !== isStatusB) return isStatusA ? 1 : -1

      return 0
    })

    return rows
  }, [auditData?.entries])

  // Consolidated entries (for summary view)
  const summaryRows = useMemo(() => {
    if (!auditData?.entries) return []
    return consolidateEntries(auditData.entries)
  }, [auditData?.entries])

  // Current rows based on view mode
  const rows = viewMode === "summary" ? summaryRows : detailedRows

  const handleExportCsv = useCallback(async () => {
    try {
      await exportCsvMutation.mutateAsync({
        filters: {
          table_name: tableName,
          record_id: recordId,
        },
        metadata: { brand, productName, lotNumber },
      })
      toast.success("CSV exported")
    } catch {
      toast.error("Failed to export CSV")
    }
  }, [tableName, recordId, brand, productName, lotNumber, exportCsvMutation])

  const handleExportPdf = useCallback(async () => {
    try {
      await exportPdfMutation.mutateAsync({
        filters: {
          table_name: tableName,
          record_id: recordId,
        },
        metadata: { brand, productName, lotNumber },
      })
      toast.success("PDF exported")
    } catch {
      toast.error("Failed to export PDF")
    }
  }, [tableName, recordId, brand, productName, lotNumber, exportPdfMutation])

  const displayTitle = title || `Audit Trail - ${tableName} #${recordId}`

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="sm:max-w-7xl max-h-[85vh] overflow-hidden flex flex-col"
        onEscapeKeyDown={(e) => e.stopPropagation()}
      >
        <DialogHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <DialogTitle>{displayTitle}</DialogTitle>
            <div className="flex items-center gap-2 mr-8">
              {/* View Mode Toggle */}
              <div className="flex items-center border rounded-md overflow-hidden">
                <button
                  onClick={() => setViewMode("summary")}
                  className={`flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    viewMode === "summary"
                      ? "bg-slate-900 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                  title="Summary view - consolidated changes"
                >
                  <Layers className="h-3.5 w-3.5" />
                  Summary
                </button>
                <button
                  onClick={() => setViewMode("detailed")}
                  className={`flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium transition-colors ${
                    viewMode === "detailed"
                      ? "bg-slate-900 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                  title="Detailed view - all field-level changes"
                >
                  <List className="h-3.5 w-3.5" />
                  Detailed
                </button>
              </div>
              <div className="w-px h-6 bg-slate-200" />
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportCsv}
                disabled={exportCsvMutation.isPending || !hasAccess}
              >
                {exportCsvMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                )}
                <span className="ml-1.5">CSV</span>
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportPdf}
                disabled={exportPdfMutation.isPending || !hasAccess}
              >
                {exportPdfMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                <span className="ml-1.5">PDF</span>
              </Button>
            </div>
          </div>
        </DialogHeader>

        {!hasAccess ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertTriangle className="h-12 w-12 text-amber-500 mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">
              Access Restricted
            </h3>
            <p className="text-sm text-slate-500 max-w-sm">
              Only QC Managers and Administrators can view audit trails.
            </p>
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertTriangle className="h-12 w-12 text-red-500 mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">
              Failed to Load Audit Trail
            </h3>
            <p className="text-sm text-slate-500">
              {error instanceof Error ? error.message : "An error occurred"}
            </p>
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Clock className="h-12 w-12 text-slate-300 mb-4" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">
              No Audit History
            </h3>
            <p className="text-sm text-slate-500">
              No changes have been recorded for this record yet.
            </p>
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-auto border rounded-lg">
            <Table>
              <TableHeader className="sticky top-0 bg-slate-50/95 backdrop-blur-sm z-10">
                <TableRow>
                  <TableHead className="w-[100px]">Date</TableHead>
                  <TableHead className="w-[70px]">User</TableHead>
                  <TableHead className="w-[75px]">Action</TableHead>
                  <TableHead className="w-[150px]">Field</TableHead>
                  <TableHead className="w-[140px]">Old</TableHead>
                  <TableHead className="w-[140px]">New</TableHead>
                  <TableHead className="w-[180px]">Reason</TableHead>
                  <TableHead className="w-[40px] text-center">
                    <MessageSquare className="h-3.5 w-3.5 inline-block" />
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {viewMode === "summary"
                  ? summaryRows.map((row, index) => (
                      <TableRow
                        key={row.id}
                        className={index % 2 === 0 ? "bg-white" : "bg-slate-100"}
                      >
                        <TableCell className="text-xs text-slate-600 font-mono align-top">
                          {row.timestampDisplay}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700 align-top">
                          {row.username}
                        </TableCell>
                        <TableCell className="align-top">
                          <Badge
                            variant={getActionBadgeVariant(row.action, row.field)}
                            className="text-xs"
                          >
                            {getActionDisplayText(row.action, row.actionDisplay, row.field)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-slate-700 align-top whitespace-normal break-words">
                          {row.field}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500 align-top whitespace-normal break-words">
                          {row.oldValue}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700 font-medium align-top whitespace-normal break-words">
                          {row.newValue}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500 italic align-top whitespace-normal break-words">
                          {row.reason || "—"}
                        </TableCell>
                        <TableCell className="text-center align-top">
                          <AnnotationPopover
                            auditId={row.primaryAuditId}
                            annotationCount={row.annotationCount}
                          />
                        </TableCell>
                      </TableRow>
                    ))
                  : detailedRows.map((row, index) => (
                      <TableRow
                        key={row.id}
                        className={index % 2 === 0 ? "bg-white" : "bg-slate-100"}
                      >
                        <TableCell className="text-xs text-slate-600 font-mono align-top">
                          {row.timestampDisplay}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700 align-top">
                          {row.username}
                        </TableCell>
                        <TableCell className="align-top">
                          <Badge
                            variant={getActionBadgeVariant(row.action, row.field)}
                            className="text-xs"
                          >
                            {getActionDisplayText(row.action, row.actionDisplay, row.field)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-slate-700 align-top whitespace-normal break-words">
                          {row.field}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500 align-top whitespace-normal break-words">
                          {row.oldValue || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700 font-medium align-top whitespace-normal break-words">
                          {row.newValue || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500 italic align-top whitespace-normal break-words">
                          {row.reason || "—"}
                        </TableCell>
                        <TableCell className="text-center align-top">
                          {row.annotationCount >= 0 && (
                            <AnnotationPopover
                              auditId={row.auditId}
                              annotationCount={row.annotationCount}
                            />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
              </TableBody>
            </Table>
          </div>
        )}

        <div className="flex-shrink-0 pt-4 border-t border-slate-200 flex justify-between items-center">
          <p className="text-xs text-slate-500">
            {viewMode === "summary" && summaryRows.length > 0 && (
              <>
                {summaryRows.length} rows
                {detailedRows.length !== summaryRows.length && (
                  <span className="text-slate-400 ml-1">
                    (from {detailedRows.length} detailed)
                  </span>
                )}
              </>
            )}
            {viewMode === "detailed" && detailedRows.length > 0 && (
              `${detailedRows.length} rows`
            )}
          </p>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default AuditTrailModal
