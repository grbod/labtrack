import { useEffect, useMemo, useState } from "react"
import { FileUp, Loader2, RotateCcw, Search, Undo2, X } from "lucide-react"
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
import type { ExtractedResultRow, LabTestType, ResultImport, ResultImportRowPreview, ResultRowAction } from "@/types"
import { cn } from "@/lib/utils"

type RowChoice = "apply" | "replace" | "skip" | "create_adhoc"

const statusLabels: Record<ResultImport["status"], string> = {
  processing: "Processing",
  needs_confirmation: "Needs confirmation",
  confirmed: "Confirmed",
  failed: "Failed",
  cancelled: "Cancelled",
  reverted: "Reverted",
}

export function ResultsImporterPage() {
  const importsQuery = useResultImports()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selectedQuery = useResultImport(selectedId)
  const selected = selectedQuery.data
  const uploadMutation = useUploadResultImports()
  const retryMutation = useRetryResultImport()
  const cancelMutation = useCancelResultImport()
  const revertMutation = useRevertResultImport()

  useEffect(() => {
    if (!selectedId && importsQuery.data?.items.length) {
      setSelectedId(importsQuery.data.items[0].id)
    }
  }, [importsQuery.data?.items, selectedId])

  const handleFiles = (files: FileList | null) => {
    const selectedFiles = Array.from(files || []).slice(0, 5)
    if (selectedFiles.length) uploadMutation.mutate(selectedFiles)
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col bg-slate-50">
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Results Importer</h1>
          <p className="mt-1 text-sm text-slate-500">Upload lab COA PDFs, review extracted rows, and apply draft results.</p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800">
          {uploadMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
          Upload PDFs
          <input
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={(event) => handleFiles(event.target.files)}
          />
        </label>
      </div>

      <div
        className="grid min-h-0 flex-1 grid-cols-[280px_minmax(360px,1fr)_520px]"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault()
          handleFiles(event.dataTransfer.files)
        }}
      >
        <ImportQueue
          items={importsQuery.data?.items || []}
          selectedId={selectedId}
          onSelect={setSelectedId}
          loading={importsQuery.isLoading}
        />
        <PdfPreview item={selected || null} />
        <ReviewPanel
          item={selected || null}
          onRetry={(id) => retryMutation.mutate(id)}
          onCancel={(id) => cancelMutation.mutate(id)}
          onRevert={(id) => revertMutation.mutate(id)}
        />
      </div>
    </div>
  )
}

function ImportQueue({
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
  return (
    <aside className="min-h-0 overflow-y-auto border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
        Queue
      </div>
      {loading ? (
        <div className="flex items-center gap-2 px-4 py-4 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading
        </div>
      ) : items.length === 0 ? (
        <div className="px-4 py-8 text-sm text-slate-500">Drop up to 5 PDFs to begin.</div>
      ) : (
        <div className="divide-y divide-slate-100">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={cn(
                "block w-full px-4 py-3 text-left hover:bg-slate-50",
                selectedId === item.id && "bg-slate-100"
              )}
            >
              <div className="truncate text-sm font-medium text-slate-900">{item.original_filename}</div>
              <div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                <span>{statusLabels[item.status]}</span>
                <span>{new Date(item.created_at).toLocaleDateString()}</span>
              </div>
              {item.duplicate_summary?.reference_number && (
                <div className="mt-1 truncate text-xs text-slate-500">
                  {item.duplicate_summary.reference_number} · {item.duplicate_summary.lot_number || "unknown lot"}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </aside>
  )
}

function PdfPreview({ item }: { item: ResultImport | null }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null
    setUrl(null)
    if (!item?.storage_key) return
    resultImportsApi.getPdfBlob(item.storage_key).then((blob) => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob)
      setUrl(objectUrl)
    })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [item?.storage_key])

  return (
    <section className="min-h-0 overflow-hidden border-r border-slate-200 bg-slate-100">
      {url ? (
        <iframe title={item?.original_filename || "PDF preview"} src={url} className="h-full w-full" />
      ) : (
        <div className="flex h-full items-center justify-center text-sm text-slate-500">
          {item ? "PDF preview loading" : "Select an import"}
        </div>
      )}
    </section>
  )
}

function ReviewPanel({
  item,
  onRetry,
  onCancel,
  onRevert,
}: {
  item: ResultImport | null
  onRetry: (id: number) => void
  onCancel: (id: number) => void
  onRevert: (id: number) => void
}) {
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)
  const [manualSearch, setManualSearch] = useState("")
  const [choices, setChoices] = useState<Record<string, RowChoice>>({})
  const [labTypeOverrides, setLabTypeOverrides] = useState<Record<string, number | null>>({})
  const [nameOverrides, setNameOverrides] = useState<Record<string, string>>({})
  const candidatesQuery = useLinkCandidates(manualSearch)
  const confirmMutation = useConfirmResultImport(item?.id || 0)
  const previewQuery = useResultImportPreview(item?.status === "needs_confirmation" ? item.id : null, selectedLotId)
  const labTypesQuery = useLabTestTypes({ page_size: 500, is_active: true })

  const rows = item?.extracted_data?.rows || []
  const candidates = item?.match_candidates || []
  const manualCandidates = candidatesQuery.data || []
  const previews = useMemo(() => {
    return new Map((previewQuery.data?.rows || []).map((row) => [row.row_id, row]))
  }, [previewQuery.data?.rows])
  const labTypes = labTypesQuery.data?.items || []

  useEffect(() => {
    const first = item?.match_candidates?.[0]
    setSelectedLotId(first?.lot_id || item?.selected_lot_id || null)
    setChoices({})
    setLabTypeOverrides({})
    setNameOverrides({})
  }, [item?.id])

  useEffect(() => {
    if (!previewQuery.data?.rows) return
    const nextChoices: Record<string, RowChoice> = {}
    const nextLabTypes: Record<string, number | null> = {}
    for (const preview of previewQuery.data.rows) {
      nextChoices[preview.row_id] = preview.suggested_action
      nextLabTypes[preview.row_id] = preview.lab_test_type_id
    }
    setChoices(nextChoices)
    setLabTypeOverrides(nextLabTypes)
  }, [item?.id, selectedLotId, previewQuery.data?.rows])

  const rowActions = useMemo<ResultRowAction[]>(() => {
    return rows.map((row) => ({
      row_id: row.row_id,
      action: choices[row.row_id] || "apply",
      lab_test_type_id: labTypeOverrides[row.row_id] ?? row.matched_lab_test_type_id,
      test_name: nameOverrides[row.row_id] || row.test_name_normalized,
    }))
  }, [choices, labTypeOverrides, nameOverrides, rows])

  if (!item) {
    return <section className="bg-white p-6 text-sm text-slate-500">Select an import to review.</section>
  }

  const canConfirm = item.status === "needs_confirmation" && selectedLotId && rows.some((row) => (choices[row.row_id] || "apply") !== "skip")

  return (
    <section className="min-h-0 overflow-y-auto bg-white">
      <div className="sticky top-0 z-10 border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-slate-900">{item.original_filename}</h2>
            <p className="mt-1 text-xs text-slate-500">{statusLabels[item.status]}</p>
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
        {item.error_message && <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{item.error_message}</div>}
      </div>

      <div className="space-y-5 p-5">
        <LotSelection
          selectedLotId={selectedLotId}
          onSelect={setSelectedLotId}
          candidates={candidates}
          manualCandidates={manualCandidates}
          manualSearch={manualSearch}
          onManualSearch={setManualSearch}
        />

        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Extracted Results</h3>
          {rows.length === 0 ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              No result rows were extracted. This import cannot be confirmed until rows are available.
            </div>
          ) : (
            <div className="overflow-hidden rounded-md border border-slate-200">
              {rows.map((row) => (
                <ResultRowReview
                  key={row.row_id}
                  row={row}
                  preview={previews.get(row.row_id) || null}
                  labTypes={labTypes}
                  choice={choices[row.row_id] || "apply"}
                  onChoice={(choice) => setChoices((current) => ({ ...current, [row.row_id]: choice }))}
                  labTestTypeId={labTypeOverrides[row.row_id] ?? row.matched_lab_test_type_id}
                  onLabTestType={(id) => {
                    setLabTypeOverrides((current) => ({ ...current, [row.row_id]: id }))
                    if (id && (choices[row.row_id] || "skip") === "skip") {
                      setChoices((current) => ({ ...current, [row.row_id]: "apply" }))
                    }
                  }}
                  nameOverride={nameOverrides[row.row_id] || ""}
                  onNameOverride={(value) => setNameOverrides((current) => ({ ...current, [row.row_id]: value }))}
                />
              ))}
            </div>
          )}
        </div>

        <Button
          disabled={!canConfirm || confirmMutation.isPending}
          onClick={() => {
            if (!selectedLotId) return
            confirmMutation.mutate({ lot_id: selectedLotId, row_actions: rowActions })
          }}
          className="w-full"
        >
          {confirmMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Apply Selected Rows as Drafts
        </Button>
      </div>
    </section>
  )
}

function LotSelection({
  selectedLotId,
  onSelect,
  candidates,
  manualCandidates,
  manualSearch,
  onManualSearch,
}: {
  selectedLotId: number | null
  onSelect: (id: number) => void
  candidates: Array<{ lot_id: number; reference_number: string; lot_number: string; status: string; score: number; reasons: string[]; products: string[] }>
  manualCandidates: Array<{ lot_id: number; reference_number: string; lot_number: string; status: string; products: string[] }>
  manualSearch: string
  onManualSearch: (value: string) => void
}) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-slate-900">Matched Lot</h3>
      <div className="space-y-2">
        {candidates.map((candidate) => (
          <button
            key={candidate.lot_id}
            onClick={() => onSelect(candidate.lot_id)}
            className={cn(
              "w-full rounded-md border px-3 py-2 text-left text-sm",
              selectedLotId === candidate.lot_id ? "border-slate-900 bg-slate-50" : "border-slate-200 hover:bg-slate-50"
            )}
          >
            <div className="font-medium text-slate-900">{candidate.reference_number} · {candidate.lot_number}</div>
            <div className="mt-1 text-xs text-slate-500">{Math.round(candidate.score * 100)}% match · {candidate.status}</div>
          </button>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-md border border-slate-200 px-2">
        <Search className="h-4 w-4 text-slate-400" />
        <input
          value={manualSearch}
          onChange={(event) => onManualSearch(event.target.value)}
          placeholder="Search lot, ref, sublot, batch"
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

function ResultRowReview({
  row,
  preview,
  labTypes,
  choice,
  onChoice,
  labTestTypeId,
  onLabTestType,
  nameOverride,
  onNameOverride,
}: {
  row: ExtractedResultRow
  preview: ResultImportRowPreview | null
  labTypes: LabTestType[]
  choice: RowChoice
  onChoice: (choice: RowChoice) => void
  labTestTypeId: number | null
  onLabTestType: (id: number | null) => void
  nameOverride: string
  onNameOverride: (value: string) => void
}) {
  const warnings = Array.from(new Set([...(row.warnings || []), ...(preview?.warnings || [])]))
  const existing = preview?.existing_result
  const needsMapping = preview?.requires_lab_test_mapping && choice !== "create_adhoc"

  return (
    <div className="border-b border-slate-100 p-3 last:border-b-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium text-slate-900">{preview?.resolved_test_name || row.test_name_normalized || row.test_name_raw}</div>
          <div className="mt-1 text-sm text-slate-600">
            {row.result_value_raw || "Blank"} {preview?.unit || row.target_unit || row.unit_raw || ""}
          </div>
          <div className="mt-1 text-xs text-slate-500">Confidence {Math.round((row.confidence || 0) * 100)}%</div>
          {existing && (
            <div className="mt-1 text-xs text-slate-500">
              Existing {existing.status}: {existing.result_value || "blank"} {existing.unit || ""}
            </div>
          )}
          {warnings.length > 0 && <div className="mt-1 text-xs text-amber-700">{warnings.join(", ")}</div>}
          {choice === "create_adhoc" && (
            <input
              value={nameOverride}
              onChange={(event) => onNameOverride(event.target.value)}
              placeholder={row.test_name_normalized || row.test_name_raw || "Ad-hoc test name"}
              className="mt-2 h-8 w-full rounded-md border border-slate-300 px-2 text-sm outline-none focus:border-slate-500"
            />
          )}
          {needsMapping && (
            <select
              value={labTestTypeId || ""}
              onChange={(event) => onLabTestType(event.target.value ? Number(event.target.value) : null)}
              className="mt-2 h-8 w-full rounded-md border border-amber-300 bg-white px-2 text-sm"
            >
              <option value="">Map lab test type</option>
              {labTypes.map((testType) => (
                <option key={testType.id} value={testType.id}>
                  {testType.test_name}
                </option>
              ))}
            </select>
          )}
        </div>
        <select
          value={choice}
          onChange={(event) => onChoice(event.target.value as RowChoice)}
          className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
        >
          <option value="apply">Apply</option>
          <option value="replace">Replace draft</option>
          <option value="create_adhoc">Create ad-hoc</option>
          <option value="skip">Skip</option>
        </select>
      </div>
    </div>
  )
}
