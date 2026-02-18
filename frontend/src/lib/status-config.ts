/**
 * Centralized status configuration for consistent styling across the app.
 * Used by SampleTable, SampleModalHeader, and other components.
 *
 * Note: KanbanBoard uses its own inline config to ensure Tailwind v4 class detection.
 */
import type { LotStatus } from "@/types"

export interface StatusConfig {
  /** Human-readable label */
  label: string
  /** Semantic color name (maps to Tailwind colors) */
  color: "sky" | "amber" | "orange" | "red" | "violet" | "indigo" | "blue" | "emerald" | "slate"
}

/**
 * Status configuration mapping.
 * Color scheme:
 * - sky: Waiting/pending states
 * - amber: In-progress states
 * - red: Attention/error states
 * - violet: Review states
 * - indigo/blue: Near completion states
 * - emerald: Success states
 * - slate: Completed/archived states
 */
export const STATUS_CONFIG: Record<LotStatus, StatusConfig> = {
  awaiting_results: { label: "Awaiting Results", color: "sky" },
  partial_results: { label: "Partial Results", color: "amber" },
  needs_attention: { label: "Needs Attention", color: "red" },
  under_review: { label: "Under Review", color: "violet" },
  awaiting_release: { label: "Awaiting Release", color: "indigo" },
  approved: { label: "Approved", color: "emerald" },
  released: { label: "Released", color: "slate" },
  rejected: { label: "Rejected", color: "red" },
}

/**
 * Get status label for display.
 */
export function getStatusLabel(status: LotStatus): string {
  return STATUS_CONFIG[status]?.label ?? status
}

/**
 * Get status color for use with Badge variant or Tailwind classes.
 */
export function getStatusColor(status: LotStatus): StatusConfig["color"] {
  return STATUS_CONFIG[status]?.color ?? "slate"
}

/**
 * Get Tailwind background classes for status (light version for badges).
 */
export function getStatusBgClasses(status: LotStatus): string {
  const color = getStatusColor(status)
  const colorClasses: Record<StatusConfig["color"], string> = {
    sky: "bg-sky-100 text-sky-700 border-sky-200",
    amber: "bg-amber-100 text-amber-700 border-amber-200",
    orange: "bg-orange-100 text-orange-700 border-orange-200",
    red: "bg-red-100 text-red-700 border-red-200",
    violet: "bg-violet-100 text-violet-700 border-violet-200",
    indigo: "bg-indigo-100 text-indigo-700 border-indigo-200",
    blue: "bg-blue-100 text-blue-700 border-blue-200",
    emerald: "bg-emerald-100 text-emerald-700 border-emerald-200",
    slate: "bg-slate-100 text-slate-700 border-slate-200",
  }
  return colorClasses[color]
}

/**
 * Get Tailwind background classes for Kanban column headers (lighter version).
 */
export function getStatusHeaderBg(status: LotStatus): string {
  const color = getStatusColor(status)
  const headerClasses: Record<StatusConfig["color"], string> = {
    sky: "bg-sky-50",
    amber: "bg-amber-50",
    orange: "bg-orange-50",
    red: "bg-red-50",
    violet: "bg-violet-50",
    indigo: "bg-indigo-50",
    blue: "bg-blue-50",
    emerald: "bg-emerald-50",
    slate: "bg-slate-50",
  }
  return headerClasses[color]
}

/**
 * Get text color class for status.
 */
export function getStatusTextColor(status: LotStatus): string {
  const color = getStatusColor(status)
  const textClasses: Record<StatusConfig["color"], string> = {
    sky: "text-sky-700",
    amber: "text-amber-700",
    orange: "text-orange-700",
    red: "text-red-700",
    violet: "text-violet-700",
    indigo: "text-indigo-700",
    blue: "text-blue-700",
    emerald: "text-emerald-700",
    slate: "text-slate-700",
  }
  return textClasses[color]
}

/**
 * Get count badge background class for status (used in Kanban columns).
 */
export function getStatusCountBg(status: LotStatus): string {
  const color = getStatusColor(status)
  const countClasses: Record<StatusConfig["color"], string> = {
    sky: "bg-sky-100",
    amber: "bg-amber-100",
    orange: "bg-orange-100",
    red: "bg-red-100",
    violet: "bg-violet-100",
    indigo: "bg-indigo-100",
    blue: "bg-blue-100",
    emerald: "bg-emerald-100",
    slate: "bg-slate-100",
  }
  return countClasses[color]
}

/**
 * Status filter options for dropdowns.
 */
export const STATUS_OPTIONS = [
  { value: "all", label: "All Statuses" },
  ...Object.entries(STATUS_CONFIG).map(([value, config]) => ({
    value,
    label: config.label,
  })),
]

/**
 * All valid lot statuses in order.
 */
export const ALL_STATUSES: LotStatus[] = [
  "awaiting_results",
  "partial_results",
  "needs_attention",
  "under_review",
  "awaiting_release",
  "approved",
  "released",
  "rejected",
]
