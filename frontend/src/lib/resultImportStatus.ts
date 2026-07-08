import type { ResultImport } from "@/types"

export const resultImportStatusLabels: Record<ResultImport["status"], string> = {
  processing: "Processing",
  needs_confirmation: "Needs review",
  confirmed: "Confirmed",
  failed: "Failed",
  cancelled: "Cancelled",
  reverted: "Reverted",
}

export const resultImportStatusDotClass: Record<ResultImport["status"], string> = {
  processing: "bg-amber-400 animate-pulse",
  needs_confirmation: "bg-blue-500",
  confirmed: "bg-emerald-500",
  failed: "bg-red-500",
  cancelled: "bg-slate-300",
  reverted: "bg-slate-300",
}

export const resultImportStatusBadgeClass: Record<ResultImport["status"], string> = {
  processing: "bg-amber-50 text-amber-700 border-amber-200",
  needs_confirmation: "bg-blue-50 text-blue-700 border-blue-200",
  confirmed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  cancelled: "bg-slate-50 text-slate-500 border-slate-200",
  reverted: "bg-slate-50 text-slate-500 border-slate-200",
}

/**
 * The lot candidate an import is (or would be) bound to: the explicitly
 * selected lot when set, otherwise the auto-select the review pane applies
 * (first candidate scoring >= 0.5). Mirrors ReviewPane's reset effect.
 */
export function bestCandidate(item: ResultImport) {
  const candidates = item.match_candidates || []
  if (item.selected_lot_id) {
    return candidates.find((c) => c.lot_id === item.selected_lot_id) ?? null
  }
  return candidates.find((c) => c.score >= 0.5) ?? null
}
