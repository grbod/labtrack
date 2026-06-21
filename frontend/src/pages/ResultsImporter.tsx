/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import {
  ChevronDown,
  FileText,
  FileUp,
  Loader2,
  RotateCcw,
  Search,
  Sparkles,
  TriangleAlert,
  Undo2,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
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
  useUploadResultImports,
} from "@/hooks/useResultImports"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import { useLotWithSpecs } from "@/hooks/useLots"
import { useTestResults } from "@/hooks/useTestResults"
import { PassFailBadge } from "@/components/domain/SampleModal/PassFailBadge"
import { calculatePassFail } from "@/lib/spec-validation"
import { buildRowActions, type SpecReviewRowState } from "@/lib/buildRowActions"
import type {
  ExtractedResultRow,
  LabTestType,
  LotType,
  ProductInLotWithSpecs,
  ResultImport,
  ResultImportCandidate,
  ResultImportRowPreview,
  TestSpecInProduct,
  TestResult,
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

const statusLabels: Record<ResultImport["status"], string> = {
  processing: "Processing",
  needs_confirmation: "Needs confirmation",
  confirmed: "Confirmed",
  failed: "Failed",
  cancelled: "Cancelled",
  reverted: "Reverted",
}

const statusDotClass: Record<ResultImport["status"], string> = {
  processing: "bg-amber-400 animate-pulse",
  needs_confirmation: "bg-blue-500",
  confirmed: "bg-emerald-500",
  failed: "bg-red-500",
  cancelled: "bg-slate-300",
  reverted: "bg-slate-300",
}

const LOT_TYPE_TAG: Record<LotType, { label: string; tag: string }> = {
  standard: { label: "Single SKU", tag: "bg-blue-100 text-blue-700" },
  parent_lot: { label: "Parent Lot", tag: "bg-green-100 text-green-700" },
  multi_sku_composite: { label: "Composite", tag: "bg-amber-100 text-amber-700" },
  sublot: { label: "Sublot", tag: "bg-slate-100 text-slate-700" },
}

const REF_COLOR = "text-amber-700"
const LOT_COLOR = "text-green-700"

// ---------------------------------------------------------------------------

export function ResultsImporterPage() {
  const importsQuery = useResultImports()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selectedQuery = useResultImport(selectedId)
  const selected = selectedQuery.data
  const uploadMutation = useUploadResultImports(setSelectedId)
  const retryMutation = useRetryResultImport()
  const cancelMutation = useCancelResultImport()
  const revertMutation = useRevertResultImport()

  const items = useMemo(() => importsQuery.data?.items || [], [importsQuery.data?.items])

  useEffect(() => {
    if (!selectedId && items.length) {
      setSelectedId(items[0].id)
    }
  }, [items, selectedId])

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const selectedFiles = Array.from(files || []).slice(0, 5)
      if (selectedFiles.length) uploadMutation.mutate(selectedFiles)
    },
    [uploadMutation]
  )

  /** Advance to the next import still awaiting confirmation (skipping `doneId`). */
  const advanceToNext = useCallback(
    (doneId: number) => {
      const next = items.find(
        (item) => item.id !== doneId && item.status === "needs_confirmation"
      )
      setSelectedId(next ? next.id : null)
    },
    [items]
  )

  const { ratio, splitRef, startDrag } = useResizableRatio()

  return (
    <div
      className="flex h-[calc(100vh-3.5rem)] flex-col bg-slate-50"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        handleFiles(event.dataTransfer.files)
      }}
    >
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-slate-900">Lab Test Import</h1>
          <p className="mt-1 text-sm text-slate-500">
            Drag lab COA PDFs to extract results, then review against the sample's spec.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <QueueDropdown
            items={items}
            selectedId={selectedId}
            onSelect={setSelectedId}
            loading={importsQuery.isLoading}
          />
          <HeaderDropzone onFiles={handleFiles} isUploading={uploadMutation.isPending} />
        </div>
      </div>

      <div ref={splitRef} className="flex min-h-0 flex-1">
        <div style={{ width: `${ratio * 100}%` }} className="min-w-0">
          <PdfPreview item={selected || null} />
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
            item={selected || null}
            onRetry={(id) => retryMutation.mutate(id)}
            onCancel={(id) => cancelMutation.mutate(id)}
            onRevert={(id) => revertMutation.mutate(id)}
            onApplied={advanceToNext}
            hasAnyImports={items.length > 0}
          />
        </div>
      </div>
    </div>
  )
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

function HeaderDropzone({
  onFiles,
  isUploading,
}: {
  onFiles: (files: FileList | null) => void
  isUploading: boolean
}) {
  const [dragOver, setDragOver] = useState(false)
  return (
    <label
      onDragOver={(event) => {
        event.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        event.stopPropagation()
        setDragOver(false)
        onFiles(event.dataTransfer.files)
      }}
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-lg border-2 border-dashed px-4 py-2 text-sm font-medium transition-colors",
        dragOver
          ? "border-blue-500 bg-blue-50 text-blue-700"
          : "border-slate-300 bg-slate-50 text-slate-600 hover:border-slate-400 hover:bg-slate-100"
      )}
    >
      {isUploading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <FileUp className="h-4 w-4" />
      )}
      <span>Drop COA PDFs</span>
      <input
        type="file"
        accept="application/pdf"
        multiple
        className="hidden"
        onChange={(event) => onFiles(event.target.files)}
      />
    </label>
  )
}

function QueueDropdown({
  items,
  selectedId,
  onSelect,
  loading,
}: {
  items: ResultImport[]
  selectedId: number | null
  onSelect: (id: number) => void
  loading: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = items.find((item) => item.id === selectedId) || null

  useEffect(() => {
    if (!open) return
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener("mousedown", onClick)
    return () => window.removeEventListener("mousedown", onClick)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex h-10 min-w-[220px] max-w-[320px] items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 hover:bg-slate-50"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Queue</span>
        {selected ? (
          <>
            <span className={cn("h-2 w-2 shrink-0 rounded-full", statusDotClass[selected.status])} />
            <span className="truncate">{selected.original_filename}</span>
          </>
        ) : (
          <span className="text-slate-400">{items.length ? "Select an import" : "Empty"}</span>
        )}
        <ChevronDown className="ml-auto h-4 w-4 shrink-0 text-slate-400" />
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-1 max-h-[60vh] w-[340px] overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
          {loading ? (
            <div className="flex items-center gap-2 px-4 py-4 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading
            </div>
          ) : items.length === 0 ? (
            <div className="px-4 py-6 text-sm text-slate-500">Drop up to 5 PDFs to begin.</div>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  onSelect(item.id)
                  setOpen(false)
                }}
                className={cn(
                  "flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-slate-50",
                  selectedId === item.id && "bg-slate-100"
                )}
              >
                <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", statusDotClass[item.status])} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-900">
                    {item.original_filename}
                  </span>
                  <span className="mt-0.5 flex items-center justify-between gap-2 text-xs text-slate-500">
                    <span>{statusLabels[item.status]}</span>
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  </span>
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
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
  hasAnyImports,
}: {
  item: ResultImport | null
  onRetry: (id: number) => void
  onCancel: (id: number) => void
  onRevert: (id: number) => void
  onApplied: (doneId: number) => void
  hasAnyImports: boolean
}) {
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)
  const [manualSearch, setManualSearch] = useState("")
  // Per-row Result-cell state: a row is "cleared" (-> skipped) when its id maps
  // to true. We do NOT carry an edited value because the backend persists the
  // original parsed `result_value_raw`; allowing free edits would silently drop
  // corrections on a regulated COA. Clearing is the only payload-affecting edit.
  const [clearedRows, setClearedRows] = useState<Record<string, boolean>>({})
  const [labTypeOverrides, setLabTypeOverrides] = useState<Record<string, number | null>>({})

  const candidatesQuery = useLinkCandidates(manualSearch)
  const confirmMutation = useConfirmResultImport(item?.id || 0)
  const previewQuery = useResultImportPreview(
    item?.status === "needs_confirmation" ? item.id : null,
    selectedLotId
  )
  const labTypesQuery = useLabTestTypes({ page_size: 500, is_active: true })
  const lotSpecsQuery = useLotWithSpecs(selectedLotId || 0)
  const lotResultsQuery = useTestResults(
    selectedLotId ? { lot_id: selectedLotId, page_size: 500 } : {}
  )

  const rows = useMemo(() => item?.extracted_data?.rows || [], [item?.extracted_data?.rows])
  const candidates = item?.match_candidates || []
  const manualCandidates = candidatesQuery.data || []
  const labTypes = labTypesQuery.data?.items || []

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
  const matchScore = candidates.find((c) => c.lot_id === selectedLotId)?.score ?? null

  // Reset per-import state when the import changes.
  useEffect(() => {
    const first = item?.match_candidates?.find((candidate) => candidate.score >= 0.5)
    setSelectedLotId(first?.lot_id || item?.selected_lot_id || null)
    setClearedRows({})
    setLabTypeOverrides({})
    setManualSearch("")
  }, [item?.id, item?.match_candidates, item?.selected_lot_id])

  const switchLot = useCallback((id: number) => {
    setSelectedLotId(id)
    setClearedRows({})
    setLabTypeOverrides({})
  }, [])

  // Build the per-row view models for the table + summary.
  const reviewRows = useMemo<ReviewRowVM[]>(
    () =>
      rows.map((row) => {
        const preview = previews.get(row.row_id)
        const onPanel = preview?.lab_test_type_id != null && panelIds.has(preview.lab_test_type_id)
        const resolvedLabTypeId = onPanel
          ? preview?.lab_test_type_id ?? null
          : labTypeOverrides[row.row_id] ?? null
        const parsedValue = row.result_value_raw ?? ""
        const cleared = !!clearedRows[row.row_id]
        const resultValue = cleared ? "" : parsedValue
        const specification = preview?.specification ?? null
        const unit = preview?.unit || row.target_unit || row.unit_raw || null
        return {
          row,
          preview: preview ?? null,
          onPanel,
          resolvedLabTypeId,
          parsedValue,
          resultValue,
          cleared,
          specification,
          unit,
          testName: preview?.resolved_test_name || row.test_name_normalized || row.test_name_raw,
          method: preview?.method ?? null,
          notes: deriveNotes(row),
          passFail: calculatePassFail(resultValue, specification, unit),
        }
      }),
    [rows, previews, panelIds, labTypeOverrides, clearedRows]
  )

  const rowActions = useMemo(() => {
    const states: SpecReviewRowState[] = reviewRows.map((vm) => ({
      row_id: vm.row.row_id,
      resultValue: vm.resultValue,
      onPanel: vm.onPanel,
      labTestTypeId: vm.resolvedLabTypeId,
      testName: vm.testName,
    }))
    return buildRowActions(states, previews)
  }, [reviewRows, previews])

  const summary = useMemo(
    () => computeSummary(reviewRows, mergedPanel, lotResultsQuery.data?.items || []),
    [reviewRows, mergedPanel, lotResultsQuery.data?.items]
  )

  if (!item) {
    return (
      <EmptyReviewState hasAnyImports={hasAnyImports} />
    )
  }

  const previewReady =
    item.status === "needs_confirmation" &&
    !!selectedLotId &&
    previewQuery.isSuccess &&
    previewQuery.data?.lot_id === selectedLotId
  const appliedCount = rowActions.filter((action) => action.action !== "skip").length
  const canConfirm = item.status === "needs_confirmation" && previewReady && appliedCount > 0

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
            {item.status === "confirmed" && (
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
                onToggleClear={(rowId, cleared) =>
                  setClearedRows((current) => ({ ...current, [rowId]: cleared }))
                }
                onMapLabType={(rowId, id) =>
                  setLabTypeOverrides((current) => ({ ...current, [rowId]: id }))
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
            </>
          )
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

function EmptyReviewState({ hasAnyImports }: { hasAnyImports: boolean }) {
  return (
    <section className="flex h-full flex-col items-center justify-center gap-3 bg-white p-10 text-center">
      <div className="rounded-2xl bg-slate-100 p-4">
        <FileUp className="h-8 w-8 text-slate-400" />
      </div>
      <p className="text-sm font-medium text-slate-700">
        {hasAnyImports ? "All caught up" : "No imports yet"}
      </p>
      <p className="max-w-xs text-sm text-slate-500">
        {hasAnyImports
          ? "Every import has been reviewed. Drop more COA PDFs to keep going."
          : "Drop lab COA PDFs above to extract results and review them here."}
      </p>
    </section>
  )
}

// --- Matched-lot card -------------------------------------------------------

function MatchedLotCard({
  product,
  lot,
  matchScore,
  panelCount,
}: {
  product: ProductInLotWithSpecs | null | undefined
  lot: { lot_number: string; reference_number: string; lot_type: LotType; status: string; products?: ProductInLotWithSpecs[] } | null
  matchScore: number | null
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
            <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[9px] font-medium text-blue-700">
              {Math.round(matchScore * 100)}% match
            </span>
          )}
        </div>
      </div>
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
  return (
    <div>
      {candidates.length > 0 && (
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
      <Chip label="Parsing now" value={summary.parsingNow} className="bg-amber-100 text-amber-800" />
      <Chip
        label="Completed / Passed"
        value={summary.completedPassed}
        className="bg-emerald-100 text-emerald-700"
      />
      <Chip
        label="Pending"
        value={summary.pending}
        className="bg-slate-100 text-slate-600"
        caption={`excludes the ${summary.parsingNowOnPanel} being imported`}
      />
      <Chip label="Other" value={summary.other} className="bg-red-100 text-red-700" caption="failed or off-panel" />
    </div>
  )
}

function Chip({
  label,
  value,
  className,
  caption,
}: {
  label: string
  value: number
  className: string
  caption?: string
}) {
  return (
    <div className={cn("rounded-md px-2.5 py-1.5", className)} title={caption}>
      <div className="flex items-baseline gap-1.5">
        <span className="text-sm font-semibold">{value}</span>
        <span className="text-[11px] font-medium">{label}</span>
      </div>
      {caption && <div className="text-[10px] opacity-70">({caption})</div>}
    </div>
  )
}

// --- Spec review table ------------------------------------------------------

function SpecReviewTable({
  rows,
  labTypes,
  onToggleClear,
  onMapLabType,
  disabled,
}: {
  rows: ReviewRowVM[]
  labTypes: LabTestType[]
  onToggleClear: (rowId: string, cleared: boolean) => void
  onMapLabType: (rowId: string, id: number | null) => void
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
              onToggleClear={(cleared) => onToggleClear(vm.row.row_id, cleared)}
              onMapLabType={(id) => onMapLabType(vm.row.row_id, id)}
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
  onToggleClear,
  onMapLabType,
  disabled,
}: {
  vm: ReviewRowVM
  labTypes: LabTestType[]
  onToggleClear: (cleared: boolean) => void
  onMapLabType: (id: number | null) => void
  disabled: boolean
}) {
  const warnings = Array.from(
    new Set([...(vm.row.warnings || []), ...(vm.preview?.warnings || [])])
  )
  const lowConfidence = (vm.row.confidence ?? 1) < 0.7
  const flagged = lowConfidence || warnings.length > 0
  const hasParsedValue = vm.parsedValue.trim() !== ""
  const existing = vm.preview?.existing_result
  const replacingDraft =
    !vm.cleared &&
    existing &&
    existing.result_value &&
    existing.result_value.trim() &&
    existing.status !== "approved"

  const offPanelSkipped = !vm.onPanel && !vm.resolvedLabTypeId

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
        </div>
        {!vm.onPanel && (
          <div className="mt-1">
            <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[9px] font-medium text-slate-600">
              Off-panel
            </span>
            <select
              value={vm.resolvedLabTypeId ?? ""}
              disabled={disabled}
              onChange={(event) =>
                onMapLabType(event.target.value ? Number(event.target.value) : null)
              }
              className="mt-1 h-7 w-full rounded-md border border-amber-300 bg-white px-1.5 text-xs text-slate-700"
            >
              <option value="">Map to apply…</option>
              {labTypes.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.test_name}
                </option>
              ))}
            </select>
          </div>
        )}
      </td>

      {/* Spec */}
      <td className="px-3 py-2 align-top font-mono text-xs text-slate-600">
        {vm.specification || "—"}
      </td>

      {/* Result: the parsed value, highlighted. Read-only because the backend
          persists the original `result_value_raw` — the only edit that changes
          the outcome is clearing the row (-> skipped). */}
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
            <span
              className={cn(
                "min-w-0 flex-1 rounded-md px-2 py-1 font-medium",
                hasParsedValue
                  ? "bg-amber-100 text-slate-900 ring-1 ring-amber-300"
                  : "text-slate-400"
              )}
            >
              {hasParsedValue ? vm.parsedValue : "Blank"}
            </span>
            {hasParsedValue && (
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
        {hasParsedValue && !vm.cleared && (
          <div className="mt-0.5 flex items-center gap-0.5 text-[10px] font-medium text-amber-600">
            <Sparkles className="h-2.5 w-2.5" /> from PDF
          </div>
        )}
        {replacingDraft && (
          <div className="mt-0.5 text-[10px] text-slate-400">
            was: <span className="line-through">{existing?.result_value}</span>
          </div>
        )}
      </td>

      {/* Unit */}
      <td className="px-3 py-2 align-top text-xs text-slate-500">{vm.unit || "—"}</td>

      {/* Method */}
      <td className="px-3 py-2 align-top text-xs text-slate-500">{vm.method || "—"}</td>

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

// --- View-model helpers -----------------------------------------------------

interface ReviewRowVM {
  row: ExtractedResultRow
  preview: ResultImportRowPreview | null
  onPanel: boolean
  resolvedLabTypeId: number | null
  parsedValue: string
  resultValue: string
  cleared: boolean
  specification: string | null
  unit: string | null
  testName: string
  method: string | null
  notes: string | null
  passFail: "pass" | "fail" | null
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
  return parts.join("; ") || null
}

interface ImportSummary {
  parsingNow: number
  /** On-panel parsed tests excluded from Pending (drives the caption count). */
  parsingNowOnPanel: number
  completedPassed: number
  pending: number
  other: number
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
 */
function computeSummary(
  reviewRows: ReviewRowVM[],
  mergedPanel: TestSpecInProduct[],
  existingResults: TestResult[]
): ImportSummary {
  const resultByLabType = new Map<number, TestResult>()
  for (const result of existingResults) {
    if (result.lab_test_type_id != null) resultByLabType.set(result.lab_test_type_id, result)
  }

  const parsingNowPanelIds = new Set(
    reviewRows
      .filter((vm) => vm.onPanel && vm.resolvedLabTypeId != null)
      .map((vm) => vm.resolvedLabTypeId as number)
  )

  let completedPassed = 0
  let pending = 0
  let otherFailed = 0

  for (const spec of mergedPanel) {
    const existing = resultByLabType.get(spec.lab_test_type_id)
    const hasValue = !!existing?.result_value && existing.result_value.trim() !== ""
    if (hasValue) {
      const pf = calculatePassFail(existing!.result_value, spec.specification, spec.test_unit)
      if (pf === "fail") otherFailed += 1
      else completedPassed += 1
    } else if (!parsingNowPanelIds.has(spec.lab_test_type_id)) {
      pending += 1
    }
  }

  const offPanelExtras = reviewRows.filter((vm) => !vm.onPanel).length

  return {
    parsingNow: reviewRows.length,
    parsingNowOnPanel: parsingNowPanelIds.size,
    completedPassed,
    pending,
    other: otherFailed + offPanelExtras,
  }
}
