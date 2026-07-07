import { useCallback, useMemo, useState } from "react"
import { FileUp, Loader2, RotateCcw, Search, TriangleAlert, Undo2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { ConfirmActionDialog } from "@/components/domain/ConfirmActionDialog"
import { ResultsImporterReviewModal } from "@/components/domain/ResultsImporterReviewModal"
import {
  useCancelResultImport,
  useResultImports,
  useRetryResultImport,
  useRevertResultImport,
  useUploadResultImports,
} from "@/hooks/useResultImports"
import {
  bestCandidate,
  resultImportStatusBadgeClass,
  resultImportStatusDotClass,
  resultImportStatusLabels,
} from "@/lib/resultImportStatus"
import { formatDate } from "@/lib/date-utils"
import { useAuthStore } from "@/store/auth"
import { hasRole } from "@/lib/roles"
import type { ResultImport } from "@/types"
import { cn } from "@/lib/utils"

type StatusFilter = "all" | ResultImport["status"]

const FILTER_CHIPS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_confirmation", label: "Needs review" },
  { key: "processing", label: "Processing" },
  { key: "confirmed", label: "Confirmed" },
  { key: "failed", label: "Failed" },
]

export function ResultsImporterListPage() {
  const user = useAuthStore((state) => state.user)
  const importsQuery = useResultImports()
  const [activeImportId, setActiveImportId] = useState<number | null>(null)
  const uploadMutation = useUploadResultImports((duplicateId) =>
    setActiveImportId(duplicateId)
  )
  const retryMutation = useRetryResultImport()
  const cancelMutation = useCancelResultImport()
  const revertMutation = useRevertResultImport()

  const [filter, setFilter] = useState<StatusFilter>("all")
  const [search, setSearch] = useState("")
  const [pendingAction, setPendingAction] = useState<
    { kind: "revert" | "cancel"; item: ResultImport } | null
  >(null)

  const items = useMemo(() => importsQuery.data?.items || [], [importsQuery.data?.items])

  const counts = useMemo(() => {
    const map = new Map<StatusFilter, number>([["all", items.length]])
    for (const item of items) {
      map.set(item.status, (map.get(item.status) || 0) + 1)
    }
    return map
  }, [items])

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return items.filter((item) => {
      if (filter !== "all" && item.status !== filter) return false
      if (!term) return true
      const candidate = bestCandidate(item)
      const haystack = [
        item.original_filename,
        candidate?.reference_number,
        candidate?.lot_number,
        ...(candidate?.products || []),
      ]
      return haystack.some((value) => value?.toLowerCase().includes(term))
    })
  }, [items, filter, search])

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const selectedFiles = Array.from(files || []).slice(0, 5)
      if (selectedFiles.length) uploadMutation.mutate(selectedFiles)
    },
    [uploadMutation]
  )

  const reviewCount = counts.get("needs_confirmation") || 0

  return (
    <div
      className="flex h-[calc(100vh-3.5rem)] flex-col bg-slate-50"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        handleFiles(event.dataTransfer.files)
      }}
    >
      <div className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-slate-900">Lab Test Import</h1>
            <p className="mt-1 text-sm text-slate-500">
              Drop lab COA PDFs to extract results, then review them against each sample's spec.
            </p>
          </div>
          {reviewCount > 0 && (
            <Button
              onClick={() => {
                const next = items.find((item) => item.status === "needs_confirmation")
                if (next) setActiveImportId(next.id)
              }}
            >
              Review {reviewCount} pending
            </Button>
          )}
        </div>

        <label
          className={cn(
            "mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm font-medium text-slate-600 transition-colors hover:border-slate-400 hover:bg-slate-100"
          )}
        >
          {uploadMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileUp className="h-4 w-4" />
          )}
          <span>Drag & drop lab COA PDFs anywhere, or click to browse (up to 5)</span>
          <input
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={(event) => {
              handleFiles(event.target.files)
              event.target.value = ""
            }}
          />
        </label>
      </div>

      <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-2.5">
        <div className="flex items-center gap-1.5">
          {FILTER_CHIPS.map((chip) => {
            const count = counts.get(chip.key) || 0
            return (
              <button
                key={chip.key}
                onClick={() => setFilter(chip.key)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                  filter === chip.key
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                )}
              >
                {chip.label} {count > 0 && <span className="opacity-70">{count}</span>}
              </button>
            )
          })}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search file, ref, lot, product..."
            className="h-8 w-64 rounded-md border border-slate-200 bg-slate-50 pl-8 pr-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:outline-none"
          />
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        {importsQuery.isLoading ? (
          <div className="flex items-center justify-center py-16 text-sm text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading imports
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={FileUp}
            title={items.length === 0 ? "No imports yet" : "No imports match"}
            description={
              items.length === 0
                ? "Drop lab COA PDFs above to extract results."
                : "Try a different filter or search term."
            }
          />
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2.5">File</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Matched Lot</th>
                  <th className="px-4 py-2.5">Product</th>
                  <th className="px-4 py-2.5">Uploaded</th>
                  <th className="px-4 py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <ImportRow
                    key={item.id}
                    item={item}
                    canRevert={
                      hasRole(user, "qc_manager", "admin") ||
                      (!!user && user.id === item.confirmed_by_id)
                    }
                    onOpen={() => setActiveImportId(item.id)}
                    onRetry={() => retryMutation.mutate(item.id)}
                    onCancel={() =>
                      item.status === "needs_confirmation"
                        ? setPendingAction({ kind: "cancel", item })
                        : cancelMutation.mutate(item.id)
                    }
                    onRevert={() => setPendingAction({ kind: "revert", item })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmActionDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null)
        }}
        title={pendingAction?.kind === "revert" ? "Revert this import?" : "Cancel this import?"}
        description={
          pendingAction?.kind === "revert"
            ? `Draft results applied from "${pendingAction.item.original_filename}" will be removed from the lot. Results that were edited or approved since are kept.`
            : `"${pendingAction?.item.original_filename}" has extracted results awaiting review. Cancelling discards them; you would need to re-upload the PDF to import it again.`
        }
        confirmLabel={pendingAction?.kind === "revert" ? "Revert import" : "Cancel import"}
        onConfirm={() => {
          if (!pendingAction) return
          if (pendingAction.kind === "revert") revertMutation.mutate(pendingAction.item.id)
          else cancelMutation.mutate(pendingAction.item.id)
        }}
      />

      <ResultsImporterReviewModal
        importId={activeImportId}
        onImportIdChange={setActiveImportId}
      />
    </div>
  )
}

function ImportRow({
  item,
  canRevert,
  onOpen,
  onRetry,
  onCancel,
  onRevert,
}: {
  item: ResultImport
  canRevert: boolean
  onOpen: () => void
  onRetry: () => void
  onCancel: () => void
  onRevert: () => void
}) {
  const candidate = bestCandidate(item)
  const candidateCount = (item.match_candidates || []).length
  const isReviewable = item.status === "needs_confirmation"

  return (
    <tr
      onClick={onOpen}
      className="cursor-pointer border-b border-slate-100 last:border-b-0 hover:bg-slate-50"
    >
      <td className="max-w-[280px] px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={cn("h-2 w-2 shrink-0 rounded-full", resultImportStatusDotClass[item.status])}
          />
          <span className="truncate font-medium text-slate-900">{item.original_filename}</span>
        </div>
        {item.error_message && (
          <p className="mt-0.5 truncate pl-4 text-xs text-red-600" title={item.error_message}>
            {item.error_message}
          </p>
        )}
      </td>
      <td className="px-4 py-3">
        <span
          className={cn(
            "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
            resultImportStatusBadgeClass[item.status]
          )}
        >
          {resultImportStatusLabels[item.status]}
        </span>
      </td>
      <td className="px-4 py-3">
        {candidate ? (
          <span className="font-mono text-xs text-slate-700">
            {candidate.reference_number}
            {!item.selected_lot_id && (
              <span className="ml-1.5 text-slate-400">{Math.round(candidate.score * 100)}%</span>
            )}
          </span>
        ) : isReviewable && candidateCount > 0 ? (
          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
            <TriangleAlert className="h-3.5 w-3.5" /> {candidateCount} candidate
            {candidateCount === 1 ? "" : "s"}
          </span>
        ) : isReviewable ? (
          <span className="text-xs text-slate-400">No match</span>
        ) : (
          <span className="text-xs text-slate-300">—</span>
        )}
      </td>
      <td className="max-w-[220px] px-4 py-3">
        <span className="block truncate text-xs text-slate-600">
          {candidate?.products?.join(", ") || "—"}
        </span>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
        {formatDate(item.created_at)}
      </td>
      <td className="px-4 py-3">
        <div
          className="flex items-center justify-end gap-1.5"
          onClick={(event) => event.stopPropagation()}
        >
          {isReviewable && (
            <Button size="sm" onClick={onOpen}>
              Review
            </Button>
          )}
          {item.status === "failed" && (
            <Button size="sm" variant="outline" onClick={onRetry}>
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" /> Retry
            </Button>
          )}
          {["processing", "needs_confirmation", "failed"].includes(item.status) && (
            <Button size="sm" variant="ghost" onClick={onCancel}>
              <X className="mr-1.5 h-3.5 w-3.5" /> Cancel
            </Button>
          )}
          {item.status === "confirmed" && canRevert && (
            <Button size="sm" variant="outline" onClick={onRevert}>
              <Undo2 className="mr-1.5 h-3.5 w-3.5" /> Revert
            </Button>
          )}
        </div>
      </td>
    </tr>
  )
}
