import type { ResultImportRowPreview, ResultRowAction } from "@/types"

export interface ExistingResultForAction {
  id: number
  result_value?: string | null
  status: string
}

/**
 * Per-row UI state for the Lab Test Import spec table. One entry per parsed
 * result row. The action posted to the backend is INFERRED from this state
 * (no apply/replace/skip/create_adhoc dropdown) by {@link buildRowActions}.
 */
export interface SpecReviewRowState {
  /** Stable extracted-row id (matches the preview row_id). */
  row_id: string
  /** Current Result cell text. Blank/whitespace => the row is skipped. */
  resultValue: string
  /** True when the parsed test maps to a required test in the lot's panel. */
  onPanel: boolean
  /**
   * Resolved lab test type id: the panel test's id for on-panel rows, or the
   * user-mapped id for off-panel rows. Null => unmapped (skipped).
   */
  labTestTypeId: number | null
  /** Test name to send for ad-hoc (off-panel) creation. */
  testName: string | null
  unit?: string | null
  specification?: string | null
  method?: string | null
}

/**
 * Pure mapper from table state to the confirm payload's `row_actions`.
 *
 * Rules (mirrors the backend confirm contract so the payload never errors):
 * - blank Result, or non-skip row with no resolved lab type      -> `skip`
 * - existing APPROVED result on the lot                           -> `skip` (immutable)
 * - existing non-empty draft/reviewed result                     -> `replace` (+ test_result_id)
 * - on-panel filled (no existing value)                          -> `apply`
 * - off-panel filled + user-mapped lab type (no existing value)  -> `create_adhoc`
 *
 * @param rows     one SpecReviewRowState per parsed row
 * @param previews backend preview rows keyed by row_id (for existing_result)
 */
export function buildRowActions(
  rows: SpecReviewRowState[],
  previews: Map<string, Pick<ResultImportRowPreview, "existing_result">>,
  existingByLabType: Map<number, ExistingResultForAction> = new Map()
): ResultRowAction[] {
  return rows.map((row) => {
    const value = (row.resultValue || "").trim()
    const base = {
      row_id: row.row_id,
      lab_test_type_id: row.labTestTypeId,
      test_name: row.testName,
      result_value: value || null,
    }
    if (!value || !row.labTestTypeId) {
      return { ...base, action: "skip" as const }
    }

    const existing =
      (row.labTestTypeId ? existingByLabType.get(row.labTestTypeId) : null) ??
      previews.get(row.row_id)?.existing_result
    if (existing) {
      if (existing.status === "approved") {
        // Approved results are immutable on the backend; never touch them.
        return { ...base, action: "skip" as const }
      }
      if (existing.result_value && existing.result_value.trim()) {
        return { ...base, action: "replace" as const, test_result_id: existing.id }
      }
      // Existing blank-draft placeholder: overwrite it in place.
      return { ...base, action: "apply" as const, test_result_id: existing.id }
    }

    if (!row.onPanel) {
      const unit = (row.unit || "").trim()
      const specification = (row.specification || "").trim()
      const method = (row.method || "").trim()
      if (!unit || !specification || !method) {
        return { ...base, action: "skip" as const }
      }
      return {
        ...base,
        action: "create_adhoc" as const,
        unit,
        specification,
        method,
      }
    }

    return {
      ...base,
      action: "apply" as const,
    }
  })
}
