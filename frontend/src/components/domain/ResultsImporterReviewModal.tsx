/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Info,
  Loader2,
  RotateCcw,
  Search,
  Sparkles,
  TriangleAlert,
  Undo2,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { ConfirmActionDialog } from "@/components/domain/ConfirmActionDialog"
import { resultImportsApi } from "@/api/resultImports"
import {
  useCancelResultImport,
  useConfirmResultImport,
  useLinkCandidates,
  useResultImport,
  useResultImportPreview,
  useResultImports,
  useRetryResultImport,
  useRevertResultImport,
} from "@/hooks/useResultImports"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import { useLotWithSpecs } from "@/hooks/useLots"
import { PassFailBadge } from "@/components/domain/SampleModal/PassFailBadge"
import { calculatePassFail } from "@/lib/spec-validation"
import { buildRowActions, type SpecReviewRowState } from "@/lib/buildRowActions"
import { useAuthStore } from "@/store/auth"
import { hasRole } from "@/lib/roles"
import {
  resultImportStatusDotClass as statusDotClass,
  resultImportStatusLabels as statusLabels,
} from "@/lib/resultImportStatus"
import type {
  ExistingResultPreview,
  ExtractedResultRow,
  LabTestType,
  LotType,
  ProductInLotWithSpecs,
  ResultImport,
  ResultImportCandidate,
  ResultImportPreviewOverride,
  ResultImportRowPreview,
  TestSpecInProduct,
} from "@/types"
import { cn } from "@/lib/utils"

import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"

// Configure PDF.js worker (matches SourcePDFViewer.tsx)
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

// --- Tunables ---------------------------------------------------------------
/** Fraction of the page's outer whitespace margin to trim so content fills the
 *  pane. Lab COAs print with ~1in margins; cropping 75% of them zooms the body
 *  text up. Single knob — raise toward 1 to crop more, 0 to disable. */
const PDF_MARGIN_CROP = 0.75
/** Approximate per-side margin as a fraction of page width (~1in on 8.5in). */
const PAGE_MARGIN_FRACTION = 0.11
const PDF_CROP_SCALE = 1 / (1 - 2 * PAGE_MARGIN_FRACTION * PDF_MARGIN_CROP)

const SPLIT_RATIO_KEY = "lab-test-import-split"
const DEFAULT_SPLIT_RATIO = 0.4

/** A processing import older than this is treated as stuck (mirrors the backend
 *  reaper window that retries/fails stalled extractions). */
const STUCK_IMPORT_MS = 20 * 60 * 1000

const LOT_TYPE_TAG: Record<LotType, { label: string; tag: string }> = {
  standard: { label: "Single SKU", tag: "bg-blue-100 text-blue-700" },
  parent_lot: { label: "Parent Lot", tag: "bg-green-100 text-green-700" },
  multi_sku_composite: { label: "Composite", tag: "bg-amber-100 text-amber-700" },
  sublot: { label: "Sublot", tag: "bg-slate-100 text-slate-700" },
}

const REF_COLOR = "text-amber-700"
const LOT_COLOR = "text-green-700"

// ---------------------------------------------------------------------------

export function ResultsImporterReviewModal({
  importId,
  onImportIdChange,
}: {
  importId: number | null
  onImportIdChange: (id: number | null) => void
}) {
  const id = importId ?? 0
  const validId = Number.isInteger(id) && id > 0

  const importsQuery = useResultImports()
  const detailQuery = useResultImport(validId ? id : null)
  const item = detailQuery.data
  const retryMutation = useRetryResultImport()
  const cancelMutation = useCancelResultImport()
  const revertMutation = useRevertResultImport()
  const [pendingAction, setPendingAction] = useState<"revert" | "cancel" | null>(null)

  const items = useMemo(() => importsQuery.data?.items || [], [importsQuery.data?.items])
  const reviewQueue = useMemo(
    () => items.filter((entry) => entry.status === "needs_confirmation"),
    [items]
  )
  const queueIndex = reviewQueue.findIndex((entry) => entry.id === id)

  /** After Apply, advance to the next import awaiting review, else close the modal. */
  const advanceToNext = useCallback(
    (doneId: number) => {
      const next = reviewQueue.find((entry) => entry.id !== doneId)
      onImportIdChange(next ? next.id : null)
    },
    [reviewQueue, onImportIdChange]
  )

  const { ratio, splitRef, startDrag } = useResizableRatio()

  return (
    <Dialog
      open={importId !== null}
      onOpenChange={(open) => {
        if (!open) onImportIdChange(null)
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="flex h-[92vh] w-[95vw] max-w-[1600px] flex-col gap-0 overflow-hidden p-0 sm:max-w-[1600px]"
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogTitle className="sr-only">
          {item?.original_filename ?? "Review imported results"}
        </DialogTitle>

        <div className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
          <div className="flex min-w-0 items-center gap-3">
            {item && (
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900">
                  {item.original_filename}
                </p>
                <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
                  <span className={cn("h-2 w-2 rounded-full", statusDotClass[item.status])} />
                  {statusLabels[item.status]}
                </p>
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {reviewQueue.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-slate-500">
                {queueIndex >= 0 ? (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={queueIndex <= 0}
                      onClick={() => onImportIdChange(reviewQueue[queueIndex - 1].id)}
                      aria-label="Previous import to review"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="whitespace-nowrap">
                      {queueIndex + 1} of {reviewQueue.length} to review
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={queueIndex >= reviewQueue.length - 1}
                      onClick={() => onImportIdChange(reviewQueue[queueIndex + 1].id)}
                      aria-label="Next import to review"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onImportIdChange(reviewQueue[0].id)}
                  >
                    {reviewQueue.length} to review <ChevronRight className="ml-1 h-4 w-4" />
                  </Button>
                )}
              </div>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onImportIdChange(null)}
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {!validId || detailQuery.isError ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm text-slate-500">
            <p>This import could not be found.</p>
            <Button variant="outline" onClick={() => onImportIdChange(null)}>
              <X className="mr-1.5 h-4 w-4" /> Close
            </Button>
          </div>
        ) : !item ? (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading import
          </div>
        ) : (
          <div ref={splitRef} className="flex min-h-0 flex-1">
            <div style={{ width: `${ratio * 100}%` }} className="min-w-0">
              <PdfPreview item={item} />
            </div>
            <div
              role="separator"
              aria-orientation="vertical"
              onPointerDown={startDrag}
              className="group relative w-1.5 shrink-0 cursor-col-resize bg-slate-200 hover:bg-blue-400"
              title="Drag to resize"
            >
              <div className="absolute inset-y-0 -left-1 -right-1" />
            </div>
            <div className="min-w-0 flex-1">
              <ReviewPane
                item={item}
                onRetry={(retryId) => retryMutation.mutate(retryId)}
                onCancel={() => setPendingAction("cancel")}
                onRevert={() => setPendingAction("revert")}
                onApplied={advanceToNext}
              />
            </div>
          </div>
        )}

        <ConfirmActionDialog
          open={pendingAction !== null}
          onOpenChange={(open) => {
            if (!open) setPendingAction(null)
          }}
          title={pendingAction === "revert" ? "Revert this import?" : "Cancel this import?"}
          description={
            pendingAction === "revert"
              ? `Draft results applied from "${item?.original_filename ?? "this PDF"}" will be removed from the lot. Results that were edited or approved since are kept.`
              : item?.status === "needs_confirmation"
                ? "Cancelling discards the extracted results; you would need to re-upload the PDF to import it again."
                : "This stops the import. You can re-upload the PDF later if needed."
          }
          confirmLabel={pendingAction === "revert" ? "Revert import" : "Cancel import"}
          onConfirm={() => {
            if (!item) return
            if (pendingAction === "revert")
              revertMutation.mutate(item.id, { onSuccess: () => onImportIdChange(null) })
            else cancelMutation.mutate(item.id, { onSuccess: () => onImportIdChange(null) })
          }}
        />
      </DialogContent>
    </Dialog>
  )
}

/** True once a processing import has stalled past STUCK_IMPORT_MS. Time is read
 *  in an effect (not during render) and re-checked periodically so the warning
 *  can appear without a status change. */
function useIsStuck(item: ResultImport): boolean {
  const [stuck, setStuck] = useState(false)
  const processing = item.status === "processing"
  const startedAt = item.updated_at || item.created_at
  useEffect(() => {
    if (!processing) {
      setStuck(false)
      return
    }
    const check = () =>
      setStuck(Date.now() - new Date(startedAt).getTime() > STUCK_IMPORT_MS)
    check()
    const timer = window.setInterval(check, 30_000)
    return () => window.clearInterval(timer)
  }, [processing, startedAt])
  return stuck
}

/** Persisted, draggable 2-pane ratio (left fraction). */
function useResizableRatio() {
  const splitRef = useRef<HTMLDivElement>(null)
  const [ratio, setRatio] = useState<number>(() => {
    const saved = Number(localStorage.getItem(SPLIT_RATIO_KEY))
    return saved >= 0.2 && saved <= 0.8 ? saved : DEFAULT_SPLIT_RATIO
  })

  const startDrag = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    const container = splitRef.current
    if (!container) return

    const onMove = (move: PointerEvent) => {
      const rect = container.getBoundingClientRect()
      const next = (move.clientX - rect.left) / rect.width
      setRatio(Math.min(0.8, Math.max(0.2, next)))
    }
    const onUp = () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      setRatio((current) => {
        localStorage.setItem(SPLIT_RATIO_KEY, String(current))
        return current
      })
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
  }, [])

  return { ratio, splitRef, startDrag }
}

function PdfPreview({ item }: { item: ResultImport | null }) {
  const [url, setUrl] = useState<string | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [pageNumber, setPageNumber] = useState(1)
  const [width, setWidth] = useState(0)
  const [loadError, setLoadError] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null
    setUrl(null)
    setNumPages(0)
    setPageNumber(1)
    setLoadError(false)
    if (!item?.storage_key) return
    resultImportsApi
      .getPdfBlob(item.storage_key)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (active) setLoadError(true)
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [item?.storage_key])

  useEffect(() => {
    const node = containerRef.current
    if (!node) return
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) setWidth(entry.contentRect.width)
      }
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [url])

  if (!item) {
    return (
      <section className="flex h-full items-center justify-center border-r border-slate-200 bg-slate-100 text-sm text-slate-500">
        Select an import to preview its COA
      </section>
    )
  }

  return (
    <section className="flex h-full flex-col border-r border-slate-200 bg-slate-100">
      {numPages > 1 && (
        <div className="flex items-center justify-center gap-3 border-b border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600">
          <button
            onClick={() => setPageNumber((value) => Math.max(1, value - 1))}
            disabled={pageNumber <= 1}
            className="rounded px-2 py-0.5 hover:bg-slate-100 disabled:opacity-40"
          >
            Prev
          </button>
          <span>
            Page {pageNumber} / {numPages}
          </span>
          <button
            onClick={() => setPageNumber((value) => Math.min(numPages, value + 1))}
            disabled={pageNumber >= numPages}
            className="rounded px-2 py-0.5 hover:bg-slate-100 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
      <div ref={containerRef} className="min-h-0 flex-1 overflow-hidden">
        {url ? (
          <div
            className="h-full w-full overflow-hidden"
            style={{ transform: `scale(${PDF_CROP_SCALE})`, transformOrigin: "top center" }}
          >
            <Document
              file={url}
              onLoadSuccess={({ numPages: pages }) => setNumPages(pages)}
              loading={
                <div className="flex h-[300px] items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              }
              error={
                <div className="flex h-[300px] flex-col items-center justify-center text-sm text-red-500">
                  <FileText className="mb-2 h-6 w-6" />
                  Failed to load PDF
                </div>
              }
            >
              {width > 0 && (
                <Page
                  pageNumber={pageNumber}
                  width={width}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                />
              )}
            </Document>
          </div>
        ) : loadError ? (
          <div className="flex h-full flex-col items-center justify-center text-sm text-red-500">
            <FileText className="mb-2 h-6 w-6" />
            Couldn't load this PDF
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading PDF
          </div>
        )}
      </div>
    </section>
  )
}

function ReviewPane({
  item,
  onRetry,
  onCancel,
  onRevert,
  onApplied,
}: {
  item: ResultImport
  onRetry: (id: number) => void
  onCancel: (id: number) => void
  onRevert: (id: number) => void
  onApplied: (doneId: number) => void
}) {
  const user = useAuthStore((state) => state.user)
  const canRevert =
    hasRole(user, "qc_manager", "admin") || (!!user && user.id === item.confirmed_by_id)
  const isStuck = useIsStuck(item)

  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)
  const [manualSearch, setManualSearch] = useState("")
  // Per-row Result-cell state. Corrections are posted in row_actions.result_value;
  // clearing a row leaves resultValue blank so the row is skipped.
  const [resultOverrides, setResultOverrides] = useState<Record<string, string>>({})
  const [clearedRows, setClearedRows] = useState<Record<string, boolean>>({})
  const [labTypeOverrides, setLabTypeOverrides] = useState<Record<string, number | null>>({})
  const [adhocMetadata, setAdhocMetadata] = useState<
    Record<string, { unit?: string; specification?: string; method?: string }>
  >({})

  const candidatesQuery = useLinkCandidates(manualSearch)
  const confirmMutation = useConfirmResultImport(item.id)
  // The operator's lab-type remaps drive a server-side re-resolve of the
  // preview: overridden rows come back with existing_result/suggested_action
  // recomputed against the mapped lab type, so the preview is the single source
  // of truth for existing-result info (no client-side lot-results shadow map).
  const previewOverrides = useMemo<ResultImportPreviewOverride[]>(
    () =>
      Object.entries(labTypeOverrides).map(([row_id, lab_test_type_id]) => ({
        row_id,
        lab_test_type_id,
      })),
    [labTypeOverrides]
  )
  const previewQuery = useResultImportPreview(
    item.status === "needs_confirmation" ? item.id : null,
    selectedLotId,
    previewOverrides
  )
  const labTypesQuery = useLabTestTypes({ page_size: 500, is_active: true })
  const lotSpecsQuery = useLotWithSpecs(selectedLotId || 0)

  const rows = useMemo(() => item.extracted_data?.rows || [], [item.extracted_data?.rows])
  const candidates = item.match_candidates || []
  const manualCandidates = candidatesQuery.data || []
  const labTypes = useMemo(() => labTypesQuery.data?.items || [], [labTypesQuery.data?.items])

  const previews = useMemo(
    () => new Map((previewQuery.data?.rows || []).map((row) => [row.row_id, row])),
    [previewQuery.data?.rows]
  )

  // Merged, deduped required panel across all products on the lot.
  const mergedPanel = useMemo(
    () => mergePanel(lotSpecsQuery.data?.products),
    [lotSpecsQuery.data?.products]
  )
  const panelIds = useMemo(
    () => new Set(mergedPanel.map((spec) => spec.lab_test_type_id)),
    [mergedPanel]
  )
  const selectedCandidate = candidates.find((c) => c.lot_id === selectedLotId) ?? null
  const matchScore = selectedCandidate?.score ?? null
  const matchReasons = selectedCandidate?.reasons ?? []

  // Reset per-import state when the import changes.
  useEffect(() => {
    const first = item?.match_candidates?.find((candidate) => candidate.score >= 0.5)
    setSelectedLotId(first?.lot_id || item?.selected_lot_id || null)
    setResultOverrides({})
    setClearedRows({})
    setLabTypeOverrides({})
    setAdhocMetadata({})
    setManualSearch("")
  }, [item?.id, item?.match_candidates, item?.selected_lot_id])

  const switchLot = useCallback((id: number) => {
    setSelectedLotId(id)
    setResultOverrides({})
    setClearedRows({})
    setLabTypeOverrides({})
    setAdhocMetadata({})
  }, [])

  // Build the per-row view models for the table + summary.
  const reviewRows = useMemo<ReviewRowVM[]>(
    () =>
      rows.map((row) => {
        const preview = previews.get(row.row_id)
        const isFuzzy = row.match_source === "fuzzy"
        const originalOnPanel =
          preview?.lab_test_type_id != null && panelIds.has(preview.lab_test_type_id)
        // Off-panel rows still inherit the backend's name-match so recognized
        // tests (e.g. Lead/Arsenic) auto-include as ad-hoc drafts. A manual
        // override (incl. clearing to null) always wins.
        const overrideId = labTypeOverrides[row.row_id]
        const resolvedLabTypeId =
          overrideId !== undefined
            ? overrideId
            : preview?.lab_test_type_id ?? null
        const onPanel = resolvedLabTypeId != null && panelIds.has(resolvedLabTypeId)
        const selectedLabType =
          resolvedLabTypeId != null ? labTypes.find((type) => type.id === resolvedLabTypeId) : null
        const parsedValue = row.result_value_raw ?? ""
        const cleared = !!clearedRows[row.row_id]
        const resultValue = cleared ? "" : resultOverrides[row.row_id] ?? parsedValue
        const metadataOverride = adhocMetadata[row.row_id] || {}
        // When the row still points at the backend-resolved lab type, the
        // preview's resolved Unit/Spec/Method are authoritative — they already
        // encode the per-serving unit for promoted metals and the lab-type
        // defaults. Only when the operator overrides to a DIFFERENT off-panel
        // type is that chosen type's catalog default the better prefill.
        const usePreview = resolvedLabTypeId === (preview?.lab_test_type_id ?? null)
        const baseSpecification = onPanel
          ? preview?.specification ?? null
          : usePreview
            ? preview?.specification || selectedLabType?.default_specification || row.limit_raw || null
            : selectedLabType?.default_specification || row.limit_raw || null
        const baseUnit = onPanel
          ? preview?.unit || row.target_unit || row.unit_raw || null
          : usePreview
            ? preview?.unit || selectedLabType?.default_unit || row.target_unit || row.unit_raw || null
            : selectedLabType?.default_unit || row.target_unit || row.unit_raw || null
        const baseMethod = onPanel
          ? preview?.method ?? null
          : usePreview
            ? preview?.method || selectedLabType?.test_method || null
            : selectedLabType?.test_method || null
        const specification = !onPanel && resolvedLabTypeId
          ? metadataOverride.specification ?? baseSpecification
          : baseSpecification
        const unit = !onPanel && resolvedLabTypeId
          ? metadataOverride.unit ?? baseUnit
          : baseUnit
        const method = !onPanel && resolvedLabTypeId
          ? metadataOverride.method ?? baseMethod
          : baseMethod
        return {
          row,
          preview: preview ?? null,
          // Existing-result info comes solely from the preview, which the backend
          // has already re-resolved against this row's override (if any).
          actionExistingResult: preview?.existing_result ?? null,
          onPanel,
          originalOnPanel,
          isFuzzy,
          matchSource: row.match_source ?? null,
          resolvedLabTypeId,
          parsedValue,
          resultValue,
          cleared,
          specification,
          unit,
          testName:
            selectedLabType?.test_name ||
            preview?.resolved_test_name ||
            row.test_name_normalized ||
            row.test_name_raw,
          method,
          isAdhoc: !onPanel && resolvedLabTypeId != null,
          notes: deriveNotes(row),
          passFail: calculatePassFail(resultValue, specification, unit),
        }
      }),
    [
      rows,
      previews,
      panelIds,
      labTypeOverrides,
      resultOverrides,
      clearedRows,
      labTypes,
      adhocMetadata,
    ]
  )

  const rowActions = useMemo(() => {
    const states: SpecReviewRowState[] = reviewRows.map((vm) => ({
      row_id: vm.row.row_id,
      resultValue: vm.resultValue,
      onPanel: vm.onPanel,
      labTestTypeId: vm.resolvedLabTypeId,
      testName: vm.testName,
      unit: vm.unit,
      specification: vm.specification,
      method: vm.method,
    }))
    return buildRowActions(states, previews)
  }, [reviewRows, previews])

  const summary = useMemo(
    () => computeSummary(reviewRows, mergedPanel, previews),
    [reviewRows, mergedPanel, previews]
  )
  const missingAdhocMetadata = reviewRows.find(
    (vm) =>
      vm.isAdhoc &&
      vm.resultValue.trim() &&
      (!vm.unit?.trim() || !vm.specification?.trim() || !vm.method?.trim())
  )
  // A fuzzy row that resolves to an already-approved result can't be applied
  // (approved results are immutable) — the operator must remap or skip it.
  const fuzzyApprovedRow = reviewRows.find(
    (vm) =>
      vm.isFuzzy &&
      !vm.cleared &&
      vm.actionExistingResult?.status === "approved"
  )

  // The preview query key encodes both the selected lot AND a stable
  // serialization of the current lab-type overrides. A settled preview
  // (isSuccess && not re-fetching) whose lot_id matches the selection is
  // therefore guaranteed to correspond to BOTH the lot and the latest overrides
  // — so row_actions built from it can never be posted from a stale preview
  // (e.g. one fetched before the operator's most recent remap).
  const previewReady =
    item.status === "needs_confirmation" &&
    !!selectedLotId &&
    previewQuery.isSuccess &&
    !previewQuery.isFetching &&
    previewQuery.data?.lot_id === selectedLotId
  const appliedCount = rowActions.filter((action) => action.action !== "skip").length
  const canConfirm =
    item.status === "needs_confirmation" &&
    previewReady &&
    appliedCount > 0 &&
    !missingAdhocMetadata
  let applyDisabledReason: string | null = null
  if (!selectedLotId) {
    applyDisabledReason = "Select a matched lot to apply."
  } else if (previewQuery.isError) {
    applyDisabledReason = "Could not load parsed row preview for this lot."
  } else if (!previewReady) {
    applyDisabledReason = "Loading parsed row preview..."
  } else if (missingAdhocMetadata) {
    applyDisabledReason = `${missingAdhocMetadata.testName} needs Unit, Spec, and Method before it can be added as an ad-hoc draft.`
  } else if (appliedCount === 0 && fuzzyApprovedRow) {
    applyDisabledReason = "Fuzzy match points to an approved result; choose an alternate test or leave it skipped."
  } else if (appliedCount === 0) {
    applyDisabledReason = "Nothing to apply yet - enter a result or map an off-panel test to an alternate."
  }

  const lotRef =
    lotSpecsQuery.data?.reference_number ||
    candidates.find((c) => c.lot_id === selectedLotId)?.reference_number ||
    "lot"

  return (
    <section className="flex h-full min-h-0 flex-col bg-white">
      <div className="border-b border-slate-200 px-5 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-900">
              {item.original_filename}
            </h2>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
              <span className={cn("h-2 w-2 rounded-full", statusDotClass[item.status])} />
              {statusLabels[item.status]}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            {item.status === "failed" && (
              <Button size="sm" variant="outline" onClick={() => onRetry(item.id)}>
                <RotateCcw className="mr-2 h-4 w-4" /> Retry
              </Button>
            )}
            {["processing", "needs_confirmation", "failed"].includes(item.status) && (
              <Button size="sm" variant="outline" onClick={() => onCancel(item.id)}>
                <X className="mr-2 h-4 w-4" /> Cancel
              </Button>
            )}
            {item.status === "confirmed" && canRevert && (
              <Button size="sm" variant="outline" onClick={() => onRevert(item.id)}>
                <Undo2 className="mr-2 h-4 w-4" /> Revert
              </Button>
            )}
          </div>
        </div>
        {item.status !== "processing" && item.error_message && (
          <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {item.error_message}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
        <MatchedLotCard
          product={mergedPanel.length ? lotSpecsQuery.data?.products?.[0] ?? null : null}
          lot={lotSpecsQuery.data ?? null}
          matchScore={matchScore}
          matchReasons={matchReasons}
          panelCount={mergedPanel.length}
        />

        <LotSwitcher
          selectedLotId={selectedLotId}
          onSelect={switchLot}
          candidates={candidates}
          manualCandidates={manualCandidates}
          manualSearch={manualSearch}
          onManualSearch={setManualSearch}
        />

        {item.status === "needs_confirmation" ? (
          rows.length === 0 ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              No result rows were extracted. This import cannot be confirmed.
            </div>
          ) : !selectedLotId ? (
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
              Select a matched lot to review the parsed tests.
            </div>
          ) : (
            <>
              <SummaryChips summary={summary} />
              <p className="text-xs text-slate-500">
                Showing only the {rows.length} test{rows.length === 1 ? "" : "s"} parsed from this
                COA — this sample requires other tests too (see summary).
              </p>
              <SpecReviewTable
                rows={reviewRows}
                labTypes={labTypes}
                onResultChange={(rowId, value) =>
                  setResultOverrides((current) => ({ ...current, [rowId]: value }))
                }
                onToggleClear={(rowId, cleared) =>
                  setClearedRows((current) => {
                    if (cleared) return { ...current, [rowId]: true }
                    const next = { ...current }
                    delete next[rowId]
                    return next
                  })
                }
                onMapLabType={(rowId, id) =>
                  setLabTypeOverrides((current) => ({ ...current, [rowId]: id }))
                }
                onMetadataChange={(rowId, field, value) =>
                  setAdhocMetadata((current) => ({
                    ...current,
                    [rowId]: { ...(current[rowId] || {}), [field]: value },
                  }))
                }
                disabled={!previewReady}
              />
              <Button
                disabled={!canConfirm || confirmMutation.isPending}
                onClick={() => {
                  if (!selectedLotId) return
                  confirmMutation.mutate(
                    { lot_id: selectedLotId, row_actions: rowActions },
                    { onSuccess: () => onApplied(item.id) }
                  )
                }}
                className="w-full"
              >
                {confirmMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Apply {appliedCount > 0 ? `${appliedCount} ` : ""}as Drafts to {lotRef}
              </Button>
              {applyDisabledReason && !confirmMutation.isPending && (
                <p className="text-center text-[11px] text-slate-500">{applyDisabledReason}</p>
              )}
            </>
          )
        ) : isStuck ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">
            <div className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <div className="space-y-1">
                <p className="font-medium">Extraction appears stuck</p>
                <p className="text-amber-700">
                  This import has been processing for over 20 minutes. The server automatically
                  retries or fails imports that stall this long, so it may recover on its own. You
                  can also cancel it and re-upload the PDF.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-1"
                  onClick={() => onCancel(item.id)}
                >
                  <X className="mr-2 h-4 w-4" /> Cancel import
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
            {item.status === "processing"
              ? "Extracting results from the PDF…"
              : `This import is ${statusLabels[item.status].toLowerCase()}.`}
          </div>
        )}
      </div>
    </section>
  )
}


function MatchedLotCard({
  product,
  lot,
  matchScore,
  matchReasons,
  panelCount,
}: {
  product: ProductInLotWithSpecs | null | undefined
  lot: { lot_number: string; reference_number: string; lot_type: LotType; status: string; products?: ProductInLotWithSpecs[] } | null
  matchScore: number | null
  matchReasons: string[]
  panelCount: number
}) {
  if (!lot) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">
        No lot selected
      </div>
    )
  }

  const typeTag = LOT_TYPE_TAG[lot.lot_type] ?? LOT_TYPE_TAG.standard
  const isComposite = lot.lot_type === "multi_sku_composite"
  const products = lot.products ?? []
  const lotNumber = lot.lot_number !== lot.reference_number ? lot.lot_number : null

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <p className="truncate text-sm font-semibold text-slate-900">
          {product?.brand || "—"}
        </p>
        <div className="flex flex-shrink-0 items-center gap-1">
          <span className={cn("rounded px-1.5 py-0.5 text-[9px] font-medium", typeTag.tag)}>
            {typeTag.label}
          </span>
          {matchScore != null && (
            <span
              className="rounded bg-blue-100 px-1.5 py-0.5 text-[9px] font-medium text-blue-700"
              title={matchReasons.length ? matchReasons.join("\n") : undefined}
            >
              {Math.round(matchScore * 100)}% match
            </span>
          )}
        </div>
      </div>
      {matchReasons.length > 0 && (
        <p className="mt-0.5 truncate text-[10px] text-slate-500" title={matchReasons.join("\n")}>
          {matchReasons[0]}
          {matchReasons.length > 1 ? ` +${matchReasons.length - 1} more` : ""}
        </p>
      )}
      {product?.product_name && (
        <p className="truncate text-xs text-slate-700">{product.product_name}</p>
      )}

      {isComposite ? (
        <div className="mt-1 space-y-0.5">
          {products.map((p) => (
            <div key={p.id} className="flex items-baseline gap-1.5 pl-2">
              <span className="truncate text-xs text-slate-500">{p.flavor ?? p.product_name}</span>
              {p.batch_number && (
                <span className="shrink-0 font-mono text-[10px] text-blue-700">{p.batch_number}</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        (product?.flavor || lotNumber) && (
          <div className="mt-0.5 flex items-baseline gap-1.5 pl-2">
            {product?.flavor && (
              <span className="truncate text-xs text-slate-500">{product.flavor}</span>
            )}
            {lotNumber && (
              <span className={cn("shrink-0 font-mono text-[10px]", LOT_COLOR)}>{lotNumber}</span>
            )}
          </div>
        )
      )}

      <div className="mt-2 flex items-center justify-between border-t border-slate-100 pt-2">
        <p className="text-[11px] text-slate-600">
          Lab Ref <span className={cn("font-mono font-medium", REF_COLOR)}>{lot.reference_number}</span>
        </p>
        <div className="flex items-center gap-1">
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-600 capitalize">
            {lot.status.replace(/_/g, " ")}
          </span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-600">
            {panelCount} tests
          </span>
        </div>
      </div>
    </div>
  )
}

function LotSwitcher({
  selectedLotId,
  onSelect,
  candidates,
  manualCandidates,
  manualSearch,
  onManualSearch,
}: {
  selectedLotId: number | null
  onSelect: (id: number) => void
  candidates: ResultImportCandidate[]
  manualCandidates: Array<{ lot_id: number; reference_number: string; lot_number: string }>
  manualSearch: string
  onManualSearch: (value: string) => void
}) {
  // Hide the switcher when there's a single candidate that's already selected —
  // the matched-lot card already shows its Lab Ref, so the chip is redundant.
  const showCandidates =
    candidates.length > 1 ||
    (candidates.length === 1 && candidates[0].lot_id !== selectedLotId)

  return (
    <div>
      {showCandidates && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {candidates.map((candidate) => (
            <button
              key={candidate.lot_id}
              onClick={() => onSelect(candidate.lot_id)}
              className={cn(
                "rounded-md border px-2 py-1 text-xs",
                selectedLotId === candidate.lot_id
                  ? "border-slate-900 bg-slate-50 text-slate-900"
                  : "border-slate-200 text-slate-600 hover:bg-slate-50"
              )}
            >
              {candidate.reference_number} · {Math.round(candidate.score * 100)}%
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2 rounded-md border border-slate-200 px-2">
        <Search className="h-4 w-4 text-slate-400" />
        <input
          value={manualSearch}
          onChange={(event) => onManualSearch(event.target.value)}
          placeholder="Switch lot — search ref, lot, sublot, batch"
          className="h-9 min-w-0 flex-1 text-sm outline-none"
        />
      </div>
      {manualCandidates.length > 0 && (
        <div className="mt-2 max-h-40 overflow-y-auto rounded-md border border-slate-200">
          {manualCandidates.map((candidate) => (
            <button
              key={candidate.lot_id}
              onClick={() => onSelect(candidate.lot_id)}
              className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
            >
              {candidate.reference_number} · {candidate.lot_number}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// --- Summary chips ----------------------------------------------------------

function SummaryChips({ summary }: { summary: ImportSummary }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Chip
        label="Parsing now"
        value={summary.parsingNow}
        className="bg-blue-100 text-blue-700"
        items={summary.parsingNowItems}
      />
      <Chip
        label="Completed / Passed"
        value={summary.completedPassed}
        className="bg-emerald-100 text-emerald-700"
        items={summary.completedPassedItems}
      />
      <Chip
        label="Pending"
        value={summary.pending}
        className="bg-slate-100 text-slate-600"
        caption={`excludes the ${summary.parsingNowOnPanel} being imported`}
        items={summary.pendingItems}
      />
      <Chip
        label="Other"
        value={summary.other}
        className="bg-amber-100 text-amber-800"
        caption="off-panel or needs attention"
        items={summary.otherItems}
        alignRight
      />
    </div>
  )
}

function Chip({
  label,
  value,
  className,
  caption,
  items,
  alignRight,
}: {
  label: string
  value: number
  className: string
  caption?: string
  items?: BucketItem[]
  alignRight?: boolean
}) {
  return (
    <div className={cn("group relative rounded-md px-2.5 py-1.5", className)}>
      <div className="flex items-baseline gap-1.5">
        <span className="text-sm font-semibold">{value}</span>
        <span className="text-[11px] font-medium">{label}</span>
      </div>
      {caption && <div className="text-[10px] opacity-70">({caption})</div>}
      {items && items.length > 0 && (
        <div
          className={cn(
            "pointer-events-none absolute top-full z-30 mt-1 hidden min-w-[14rem] max-w-xs rounded-md border border-slate-200 bg-white p-2 text-left shadow-lg group-hover:block",
            alignRight ? "right-0" : "left-0"
          )}
        >
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
            {label}
          </p>
          <ul className="space-y-0.5">
            {items.map((bucketItem, idx) => (
              <li key={idx} className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="truncate text-slate-700">{bucketItem.name}</span>
                <span className="shrink-0 text-slate-400">
                  {bucketItem.value ? bucketItem.value : bucketItem.reason}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// --- Spec review table ------------------------------------------------------

function SpecReviewTable({
  rows,
  labTypes,
  onResultChange,
  onToggleClear,
  onMapLabType,
  onMetadataChange,
  disabled,
}: {
  rows: ReviewRowVM[]
  labTypes: LabTestType[]
  onResultChange: (rowId: string, value: string) => void
  onToggleClear: (rowId: string, cleared: boolean) => void
  onMapLabType: (rowId: string, id: number | null) => void
  onMetadataChange: (
    rowId: string,
    field: "unit" | "specification" | "method",
    value: string
  ) => void
  disabled: boolean
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-[11px] uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2 font-semibold" style={{ width: "22%" }}>Test</th>
            <th className="px-3 py-2 font-semibold" style={{ width: "11%" }}>Spec</th>
            <th className="px-3 py-2 font-semibold" style={{ width: "18%" }}>Result</th>
            <th className="px-3 py-2 font-semibold" style={{ width: "8%" }}>Unit</th>
            <th className="px-3 py-2 font-semibold" style={{ width: "12%" }}>Method</th>
            <th className="px-3 py-2 font-semibold" style={{ width: "16%" }}>Notes</th>
            <th className="px-3 py-2 font-semibold" style={{ width: "13%" }}>Pass/Fail</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((vm) => (
            <SpecReviewRow
              key={vm.row.row_id}
              vm={vm}
              labTypes={labTypes}
              onResultChange={(value) => onResultChange(vm.row.row_id, value)}
              onToggleClear={(cleared) => onToggleClear(vm.row.row_id, cleared)}
              onMapLabType={(id) => onMapLabType(vm.row.row_id, id)}
              onMetadataChange={(field, value) =>
                onMetadataChange(vm.row.row_id, field, value)
              }
              disabled={disabled}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SpecReviewRow({
  vm,
  labTypes,
  onResultChange,
  onToggleClear,
  onMapLabType,
  onMetadataChange,
  disabled,
}: {
  vm: ReviewRowVM
  labTypes: LabTestType[]
  onResultChange: (value: string) => void
  onToggleClear: (cleared: boolean) => void
  onMapLabType: (id: number | null) => void
  onMetadataChange: (field: "unit" | "specification" | "method", value: string) => void
  disabled: boolean
}) {
  const warnings = Array.from(
    new Set([...(vm.row.warnings || []), ...(vm.preview?.warnings || [])])
  )
  const lowConfidence = (vm.row.confidence ?? 1) < 0.7
  const flagged = lowConfidence || warnings.length > 0
  const aliasNotice = getAliasNotice(vm)
  const hasResultValue = vm.resultValue.trim() !== ""
  const edited = !vm.cleared && vm.resultValue !== vm.parsedValue
  const existing = vm.actionExistingResult
  const approvedExisting = existing?.status === "approved"
  const replacingDraft =
    !vm.cleared &&
    existing &&
    existing.result_value &&
    existing.result_value.trim() &&
    existing.status !== "approved"

  const offPanelSkipped = !vm.onPanel && !vm.resolvedLabTypeId
  const showMappingControl = !vm.originalOnPanel || vm.isFuzzy
  // A fuzzy row already auto-resolved to a target; keep the override combobox
  // tucked behind a compact control so the common (accept-the-fuzzy) case stays
  // clean. Genuinely-unmapped rows always show the picker.
  const [showOverride, setShowOverride] = useState(false)
  const isResolvedFuzzy = vm.isFuzzy && vm.resolvedLabTypeId != null

  return (
    <tr
      className={cn(
        "border-b border-slate-100 last:border-b-0",
        offPanelSkipped && "bg-slate-50 text-slate-400"
      )}
    >
      {/* Test */}
      <td className="px-3 py-2 align-top">
        <div className="flex items-center gap-1">
          <span className={cn("font-medium", offPanelSkipped ? "text-slate-500" : "text-slate-900")}>
            {vm.testName}
          </span>
          {flagged && (
            <span
              title={[
                lowConfidence ? "Low extraction confidence" : null,
                ...warnings,
              ]
                .filter(Boolean)
                .join(" · ")}
            >
              <TriangleAlert className="h-3.5 w-3.5 text-amber-500" />
            </span>
          )}
          {aliasNotice && (
            <span title={aliasNotice}>
              <Info className="h-3.5 w-3.5 text-sky-500" />
            </span>
          )}
        </div>
        {showMappingControl && (
          <div className="mt-1 space-y-1">
            <div className="flex items-center gap-1">
              {!vm.onPanel && (
                <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[9px] font-medium text-slate-600">
                  Off-panel
                </span>
              )}
              {vm.isFuzzy && (
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-700">
                  Fuzzy match
                </span>
              )}
              {vm.resolvedLabTypeId != null && (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-medium text-emerald-700">
                  {vm.onPanel ? "On-panel draft" : "Ad-hoc draft"}
                </span>
              )}
            </div>
            {vm.resolvedLabTypeId == null && (
              <p className="text-[10px] text-slate-400">
                Pick a lab test type to include this row, or leave it skipped.
              </p>
            )}
            {isResolvedFuzzy && !showOverride ? (
              <button
                type="button"
                disabled={disabled}
                onClick={() => setShowOverride(true)}
                className="text-[10px] font-medium text-blue-600 hover:underline disabled:opacity-50"
              >
                Override mapping
              </button>
            ) : (
              <LabTypeCombobox
                value={vm.resolvedLabTypeId}
                labTypes={labTypes}
                disabled={disabled}
                onChange={onMapLabType}
              />
            )}
          </div>
        )}
      </td>

      {/* Spec */}
      <td className="px-3 py-2 align-top font-mono text-xs text-slate-600">
        {vm.isAdhoc ? (
          <input
            value={vm.specification || ""}
            disabled={disabled}
            onChange={(event) => onMetadataChange("specification", event.target.value)}
            placeholder="Spec"
            className="h-7 w-full rounded-md border border-amber-300 bg-white px-1.5 font-mono text-xs text-slate-700 outline-none focus:border-amber-400"
          />
        ) : (
          vm.specification || "—"
        )}
      </td>

      {/* Result */}
      <td className="px-3 py-2 align-top">
        {vm.cleared ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => onToggleClear(false)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-400 hover:bg-slate-50 disabled:opacity-50"
          >
            <Undo2 className="h-3 w-3" /> Skipped — restore
          </button>
        ) : (
          <div className="flex items-start gap-1">
            <input
              value={vm.resultValue}
              disabled={disabled}
              onChange={(event) => onResultChange(event.target.value)}
              placeholder="Blank"
              className={cn(
                "min-w-0 flex-1 rounded-md px-2 py-1 font-medium outline-none",
                hasResultValue
                  ? "bg-amber-100 text-slate-900 ring-1 ring-amber-300"
                  : "bg-white text-slate-400 ring-1 ring-slate-200",
                edited && "ring-blue-300"
              )}
            />
            {hasResultValue && (
              <button
                type="button"
                disabled={disabled}
                onClick={() => onToggleClear(true)}
                title="Clear (skip this row)"
                className="mt-0.5 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}
        {!vm.cleared && hasResultValue && (
          <div
            className={cn(
              "mt-0.5 flex items-center gap-0.5 text-[10px] font-medium",
              edited ? "text-blue-600" : "text-amber-600"
            )}
          >
            <Sparkles className="h-2.5 w-2.5" />
            {edited ? `edited; PDF: ${vm.parsedValue || "Blank"}` : "from PDF"}
          </div>
        )}
        {replacingDraft && (
          <div className="mt-0.5 text-[10px] text-slate-400">
            was: <span className="line-through">{existing?.result_value}</span>
          </div>
        )}
        {approvedExisting && (
          <div className="mt-0.5 text-[10px] text-slate-400">
            Approved result exists - skipped
          </div>
        )}
      </td>

      {/* Unit */}
      <td className="px-3 py-2 align-top text-xs text-slate-500">
        {vm.isAdhoc ? (
          <input
            value={vm.unit || ""}
            disabled={disabled}
            onChange={(event) => onMetadataChange("unit", event.target.value)}
            placeholder="Unit"
            className="h-7 w-full rounded-md border border-amber-300 bg-white px-1.5 text-xs text-slate-700 outline-none focus:border-amber-400"
          />
        ) : (
          vm.unit || "—"
        )}
      </td>

      {/* Method */}
      <td className="px-3 py-2 align-top text-xs text-slate-500">
        {vm.isAdhoc ? (
          <input
            value={vm.method || ""}
            disabled={disabled}
            onChange={(event) => onMetadataChange("method", event.target.value)}
            placeholder="Method"
            className="h-7 w-full rounded-md border border-amber-300 bg-white px-1.5 text-xs text-slate-700 outline-none focus:border-amber-400"
          />
        ) : (
          vm.method || "—"
        )}
      </td>

      {/* Notes (parsed; saved server-side on confirm) */}
      <td className="px-3 py-2 align-top text-xs text-slate-500">
        {vm.notes ? (
          <span className="line-clamp-2" title={vm.notes}>
            {vm.notes}
          </span>
        ) : (
          "—"
        )}
      </td>

      {/* Pass/Fail */}
      <td className="px-3 py-2 align-top">
        <PassFailBadge status={vm.passFail} />
      </td>
    </tr>
  )
}

/**
 * Searchable "Map to Alternate" picker for off-panel rows. Filters the full
 * active lab-test-type catalog by name or abbreviation so e.g. "arsenic"/"as"
 * finds Arsenic without scrolling a 200+ entry native select.
 */
function LabTypeCombobox({
  value,
  labTypes,
  disabled,
  onChange,
}: {
  value: number | null
  labTypes: LabTestType[]
  disabled: boolean
  onChange: (id: number | null) => void
}) {
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const selected = labTypes.find((t) => t.id === value) ?? null
  const q = query.trim().toLowerCase()
  const matches = (
    q
      ? labTypes.filter(
          (t) =>
            t.test_name.toLowerCase().includes(q) ||
            (t.abbreviations || "").toLowerCase().includes(q)
        )
      : labTypes
  ).slice(0, 8)

  return (
    <div className="relative">
      <div className="flex items-center gap-1">
        <input
          value={open ? query : selected?.test_name ?? ""}
          disabled={disabled}
          placeholder="Map to Alternate…"
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onBlur={() =>
            window.setTimeout(() => {
              setOpen(false)
              setQuery("")
            }, 120)
          }
          className="h-7 w-full rounded-md border border-amber-300 bg-white px-1.5 text-xs text-slate-700 outline-none focus:border-amber-400"
        />
        {selected && !disabled && (
          <button
            type="button"
            title="Clear mapping"
            onMouseDown={(event) => {
              event.preventDefault()
              onChange(null)
              setQuery("")
              setOpen(false)
            }}
            className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
      {open && matches.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
          {matches.map((type) => (
            <li key={type.id}>
              <button
                type="button"
                onMouseDown={(event) => {
                  event.preventDefault()
                  onChange(type.id)
                  setQuery("")
                  setOpen(false)
                }}
                className={cn(
                  "block w-full px-2 py-1.5 text-left text-xs hover:bg-slate-50",
                  type.id === value ? "font-medium text-slate-900" : "text-slate-600"
                )}
              >
                {type.test_name}
                {type.test_category && (
                  <span className="ml-1 text-[10px] text-slate-400">{type.test_category}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// --- View-model helpers -----------------------------------------------------

interface ReviewRowVM {
  row: ExtractedResultRow
  preview: ResultImportRowPreview | null
  actionExistingResult: ExistingResultPreview | null
  onPanel: boolean
  originalOnPanel: boolean
  isFuzzy: boolean
  matchSource: ExtractedResultRow["match_source"]
  resolvedLabTypeId: number | null
  parsedValue: string
  resultValue: string
  cleared: boolean
  specification: string | null
  unit: string | null
  testName: string
  method: string | null
  isAdhoc: boolean
  notes: string | null
  passFail: "pass" | "fail" | null
}

function getAliasNotice(vm: ReviewRowVM) {
  if (vm.matchSource === "builtin_alias") {
    return `Matched PDF wording "${vm.row.test_name_raw}" to "${vm.testName}" using built-in normalization.`
  }
  if (vm.matchSource === "approved_alias") {
    return `Matched approved alias "${vm.row.test_name_raw}" to "${vm.testName}".`
  }
  return null
}

/**
 * Display note mirroring the backend's `_row_notes` (which is what gets saved on
 * confirm): lab-reported unit/limit and any LOD/LOQ/per-serving metadata.
 */
function deriveNotes(row: ExtractedResultRow): string | null {
  const metadata = row.metadata || {}
  const parts: string[] = []
  if (row.unit_raw && row.unit_raw !== row.target_unit) parts.push(`Lab unit: ${row.unit_raw}`)
  if (row.limit_raw) parts.push(`Lab limit: ${row.limit_raw}`)
  for (const key of ["lod", "loq", "per_serving"]) {
    const value = metadata[key]
    if (value) parts.push(`${key.toUpperCase()}: ${String(value)}`)
  }
  if (metadata.mass_basis_value) {
    const unit = metadata.mass_basis_unit || "ug/g"
    parts.push(`Mass basis: ${String(metadata.mass_basis_value)} ${String(unit)}`)
  }
  return parts.join("; ") || null
}

interface BucketItem {
  name: string
  value?: string | null
  reason?: string
}

interface ImportSummary {
  parsingNow: number
  /** On-panel parsed tests excluded from Pending (drives the caption count). */
  parsingNowOnPanel: number
  completedPassed: number
  pending: number
  other: number
  parsingNowItems: BucketItem[]
  completedPassedItems: BucketItem[]
  pendingItems: BucketItem[]
  otherItems: BucketItem[]
}

/** Union of all products' required specs, deduped by lab_test_type_id (first wins). */
function mergePanel(products?: ProductInLotWithSpecs[]): TestSpecInProduct[] {
  if (!products?.length) return []
  const seen = new Set<number>()
  const merged: TestSpecInProduct[] = []
  for (const product of products) {
    for (const spec of product.test_specifications || []) {
      if (!spec.is_required) continue
      if (seen.has(spec.lab_test_type_id)) continue
      seen.add(spec.lab_test_type_id)
      merged.push(spec)
    }
  }
  return merged
}

/**
 * Reconcile the parsed rows against the lot's required panel + existing results
 * into the four summary buckets. Each panel test lands in exactly one of
 * Completed/Passed, Pending, or Other(failed); off-panel parsed rows add to Other.
 *
 * Existing-result info is drawn from the preview rows (the backend re-resolves
 * each row's existing_result against its resolved lab type), so the summary
 * reflects the same existing results the action-builder acts on.
 */
function computeSummary(
  reviewRows: ReviewRowVM[],
  mergedPanel: TestSpecInProduct[],
  previews: Map<string, ResultImportRowPreview>
): ImportSummary {
  const resultByLabType = new Map<number, ExistingResultPreview>()
  for (const preview of previews.values()) {
    if (preview.lab_test_type_id != null && preview.existing_result != null) {
      if (!resultByLabType.has(preview.lab_test_type_id)) {
        resultByLabType.set(preview.lab_test_type_id, preview.existing_result)
      }
    }
  }

  const parsingRows = reviewRows.filter(
    (vm) =>
      vm.resultValue.trim() &&
      vm.resolvedLabTypeId != null &&
      vm.actionExistingResult?.status !== "approved"
  )

  const parsingNowPanelIds = new Set(
    parsingRows
      .filter((vm) => vm.onPanel)
      .map((vm) => vm.resolvedLabTypeId as number)
  )

  const completedPassedItems: BucketItem[] = []
  const pendingItems: BucketItem[] = []
  const otherItems: BucketItem[] = []

  for (const spec of mergedPanel) {
    const existing = resultByLabType.get(spec.lab_test_type_id)
    const hasValue = !!existing?.result_value && existing.result_value.trim() !== ""
    if (hasValue) {
      const pf = calculatePassFail(existing!.result_value, spec.specification, spec.test_unit)
      if (pf === "fail") {
        otherItems.push({ name: spec.test_name, value: existing!.result_value, reason: "Failed" })
      } else {
        completedPassedItems.push({
          name: spec.test_name,
          value: existing!.result_value,
          reason: "Passed",
        })
      }
    } else if (!parsingNowPanelIds.has(spec.lab_test_type_id)) {
      pendingItems.push({ name: spec.test_name, reason: "Awaiting results" })
    }
  }

  const parsingNowItems: BucketItem[] = parsingRows.map((vm) => ({
    name: vm.testName,
    value: vm.resultValue,
    reason: vm.onPanel
      ? "On panel"
      : vm.resolvedLabTypeId != null
        ? "Off-panel · ad-hoc draft"
        : "Off-panel · needs mapping",
  }))

  for (const vm of parsingRows) {
    if (!vm.onPanel) {
      otherItems.push({
        name: vm.testName,
        value: vm.resultValue,
        reason: vm.resolvedLabTypeId != null ? "Off-panel · ad-hoc draft" : "Off-panel · needs mapping",
      })
    }
  }

  return {
    parsingNow: parsingRows.length,
    parsingNowOnPanel: parsingNowPanelIds.size,
    completedPassed: completedPassedItems.length,
    pending: pendingItems.length,
    other: otherItems.length,
    parsingNowItems,
    completedPassedItems,
    pendingItems,
    otherItems,
  }
}
