import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { AdditionalTestsAccordion } from "./AdditionalTestsAccordion"
import type { LabTestType, TestResultRow } from "@/types"

const labTestTypes = [
  {
    id: 7,
    test_name: "Organoleptic Evaluation",
    test_category: "Organoleptic",
    default_unit: "n/a",
    test_method: "In-house",
    default_specification: "Conforms",
    description: null,
    abbreviations: null,
    is_active: true,
    archived_at: null,
    archived_by_id: null,
    archive_reason: null,
    created_at: "2024-01-01",
    updated_at: null,
  },
] as LabTestType[]

function makeRow(overrides: Partial<TestResultRow> = {}): TestResultRow {
  return {
    id: 1,
    lot_id: 10,
    test_type: "Organoleptic Evaluation",
    result_value: null,
    unit: "n/a",
    specification: "Conforms",
    method: "In-house",
    notes: null,
    test_date: null,
    pdf_source: null,
    confidence_score: null,
    status: "draft",
    approved_by_id: null,
    approved_at: null,
    created_at: "2024-01-01",
    updated_at: null,
    lab_test_type_id: 7,
    include_on_coa: true,
    passFailStatus: null,
    isFlagged: false,
    isAdditionalTest: true,
    ...overrides,
  }
}

describe("AdditionalTestsAccordion", () => {
  it("shows matching test types in dropdown and adds with id", async () => {
    const onAddTest = vi.fn().mockResolvedValue(undefined)
    render(
      <AdditionalTestsAccordion
        additionalTests={[]}
        labTestTypes={labTestTypes}
        onUpdateResult={vi.fn()}
        onAddTest={onAddTest}
      />
    )
    fireEvent.click(screen.getByText(/Additional Tests/))
    fireEvent.click(screen.getByText("Add Test"))
    fireEvent.change(screen.getByPlaceholderText("Search test types..."), {
      target: { value: "organolep" },
    })
    const option = await screen.findByText("Organoleptic Evaluation")
    fireEvent.click(option)
    expect(onAddTest).toHaveBeenCalledWith("Organoleptic Evaluation", 7)
  })

  it("shows remove button for rows without result_value, hides it for rows with a value", () => {
    const onDeleteResult = vi.fn().mockResolvedValue(undefined)
    const rowWithResult = makeRow({ id: 1, result_value: "Conforms" })
    const rowWithoutResult = makeRow({ id: 2, result_value: null })

    render(
      <AdditionalTestsAccordion
        additionalTests={[rowWithResult, rowWithoutResult]}
        labTestTypes={labTestTypes}
        onUpdateResult={vi.fn()}
        onAddTest={vi.fn()}
        onDeleteResult={onDeleteResult}
      />
    )
    // Expand the accordion
    fireEvent.click(screen.getByText(/Additional Tests/))

    // Row with result should NOT show delete button
    // Row without result SHOULD show delete button
    const deleteButtons = screen.getAllByTitle("Remove test")
    expect(deleteButtons).toHaveLength(1)
  })

  it("calls onToggleCoa with false when the include-on-COA checkbox is unchecked", () => {
    const onToggleCoa = vi.fn().mockResolvedValue(undefined)
    const row = makeRow({ id: 5, include_on_coa: true, result_value: "Conforms" })

    render(
      <AdditionalTestsAccordion
        additionalTests={[row]}
        labTestTypes={labTestTypes}
        onUpdateResult={vi.fn()}
        onAddTest={vi.fn()}
        onToggleCoa={onToggleCoa}
      />
    )
    fireEvent.click(screen.getByText(/Additional Tests/))

    const checkbox = screen.getByTitle("Include on COA")
    fireEvent.click(checkbox)
    expect(onToggleCoa).toHaveBeenCalledWith(5, false)
  })
})
