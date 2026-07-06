import { describe, it, expect } from "vitest"
import { buildRowActions, type SpecReviewRowState } from "./buildRowActions"
import type { ResultImportRowPreview } from "@/types"

type PreviewSlice = Pick<ResultImportRowPreview, "existing_result">

function previewMap(
  entries: Record<string, ResultImportRowPreview["existing_result"]>
): Map<string, PreviewSlice> {
  return new Map(
    Object.entries(entries).map(([row_id, existing_result]) => [row_id, { existing_result }])
  )
}

const onPanelRow = (over: Partial<SpecReviewRowState> = {}): SpecReviewRowState => ({
  row_id: "r1",
  resultValue: "1,300",
  onPanel: true,
  labTestTypeId: 42,
  testName: "Total Plate Count",
  ...over,
})

describe("buildRowActions", () => {
  it("maps a filled on-panel row with no existing result to apply", () => {
    const [action] = buildRowActions([onPanelRow()], previewMap({ r1: null }))
    expect(action).toMatchObject({
      row_id: "r1",
      action: "apply",
      lab_test_type_id: 42,
      result_value: "1,300",
    })
    expect(action.test_result_id).toBeUndefined()
  })

  it("drops editable unit/spec/method from an on-panel apply payload", () => {
    const [action] = buildRowActions(
      [onPanelRow({ unit: "WRONG", specification: "WRONG", method: "WRONG" })],
      previewMap({ r1: null })
    )
    expect(action.action).toBe("apply")
    expect("unit" in action).toBe(false)
    expect("specification" in action).toBe(false)
    expect("method" in action).toBe(false)
  })

  it("maps an on-panel row with an existing non-empty draft to replace + test_result_id", () => {
    const previews = previewMap({
      r1: { id: 99, test_type: "Total Plate Count", result_value: "900", unit: "CFU/g", status: "draft", test_date: null, pdf_source: null },
    })
    const [action] = buildRowActions([onPanelRow()], previews)
    expect(action).toMatchObject({ action: "replace", test_result_id: 99 })
  })

  it("overwrites an existing blank-draft placeholder with apply", () => {
    const previews = previewMap({
      r1: { id: 7, test_type: "Total Plate Count", result_value: "", unit: null, status: "draft", test_date: null, pdf_source: null },
    })
    const [action] = buildRowActions([onPanelRow()], previews)
    expect(action).toMatchObject({ action: "apply", test_result_id: 7 })
  })

  it("never modifies an approved result (skips it)", () => {
    const previews = previewMap({
      r1: { id: 5, test_type: "Total Plate Count", result_value: "900", unit: "CFU/g", status: "approved", test_date: null, pdf_source: null },
    })
    const [action] = buildRowActions([onPanelRow()], previews)
    expect(action.action).toBe("skip")
  })

  it("maps an off-panel row mapped to a lab type to create_adhoc", () => {
    const row = onPanelRow({
      row_id: "r2",
      onPanel: false,
      labTestTypeId: 88,
      testName: "Lead",
      unit: "ppm",
      specification: "< 0.5 ppm",
      method: "ICP-MS",
    })
    const [action] = buildRowActions([row], previewMap({ r2: null }))
    expect(action).toMatchObject({
      action: "create_adhoc",
      lab_test_type_id: 88,
      test_name: "Lead",
      unit: "ppm",
      specification: "< 0.5 ppm",
      method: "ICP-MS",
    })
  })

  it("skips an off-panel mapped row when ad-hoc metadata is missing", () => {
    const row = onPanelRow({
      row_id: "r2",
      onPanel: false,
      labTestTypeId: 88,
      testName: "Lead",
      unit: "ppm",
      specification: "",
      method: "ICP-MS",
    })
    const [action] = buildRowActions([row], previewMap({ r2: null }))
    expect(action.action).toBe("skip")
  })

  it("maps an off-panel row mapped to an existing draft lab type to replace", () => {
    const row = onPanelRow({ row_id: "r2", onPanel: false, labTestTypeId: 88, testName: "Lead" })
    const existingByLabType = new Map([
      [88, { id: 123, result_value: "0.11", status: "draft" }],
    ])
    const [action] = buildRowActions([row], previewMap({ r2: null }), existingByLabType)
    expect(action).toMatchObject({ action: "replace", test_result_id: 123, lab_test_type_id: 88 })
  })

  it("skips an off-panel row mapped to an approved lab type result", () => {
    const row = onPanelRow({ row_id: "r2", onPanel: false, labTestTypeId: 88, testName: "Lead" })
    const existingByLabType = new Map([
      [88, { id: 123, result_value: "0.11", status: "approved" }],
    ])
    const [action] = buildRowActions([row], previewMap({ r2: null }), existingByLabType)
    expect(action.action).toBe("skip")
  })

  it("skips an on-panel override mapped to an approved lab type result", () => {
    const row = onPanelRow({ row_id: "r4", onPanel: true, labTestTypeId: 88, testName: "Lead" })
    const existingByLabType = new Map([
      [88, { id: 123, result_value: "0.11", status: "approved" }],
    ])
    const [action] = buildRowActions([row], previewMap({ r4: null }), existingByLabType)
    expect(action.action).toBe("skip")
  })

  it("skips an off-panel row that has not been mapped yet", () => {
    const row = onPanelRow({ row_id: "r3", onPanel: false, labTestTypeId: null })
    const [action] = buildRowActions([row], previewMap({ r3: null }))
    expect(action.action).toBe("skip")
  })

  it("skips a blank/cleared Result cell", () => {
    const row = onPanelRow({ resultValue: "   " })
    const [action] = buildRowActions([row], previewMap({ r1: null }))
    expect(action.action).toBe("skip")
  })

  it("handles a mix of rows independently", () => {
    const rows: SpecReviewRowState[] = [
      onPanelRow({ row_id: "a" }),
      onPanelRow({ row_id: "b", resultValue: "" }),
      onPanelRow({
        row_id: "c",
        onPanel: false,
        labTestTypeId: 12,
        testName: "Arsenic",
        unit: "ppm",
        specification: "< 0.2 ppm",
        method: "ICP-MS",
      }),
    ]
    const actions = buildRowActions(rows, previewMap({ a: null, b: null, c: null }))
    expect(actions.map((a) => a.action)).toEqual(["apply", "skip", "create_adhoc"])
  })
})
