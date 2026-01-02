import { useState, useCallback, useMemo } from "react"
import { createColumnHelper, type ColumnDef } from "@tanstack/react-table"
import { nanoid } from "nanoid"
import { BulkImportGrid, createEditableCell } from "./BulkImportGrid"
import { useBulkImportLabTestTypes } from "@/hooks/useLabTestTypes"
import {
  labTestTypeGridSchema,
  type LabTestTypeGridRow,
  validateRow as validateRowSchema,
} from "@/lib/bulk-import/validators"
import {
  exportTemplate,
  parseExcelFile,
} from "@/lib/bulk-import/excel-utils"
import type { EditingCell } from "./types"
import { Input } from "@/components/ui/input"

// Test categories from your domain
const TEST_CATEGORIES = [
  "Microbiological",
  "Heavy Metals",
  "Nutritional",
  "Contaminants",
  "Physical",
  "Other",
] as const

const createEmptyRow = (): LabTestTypeGridRow => ({
  id: nanoid(),
  test_name: "",
  test_category: "",
  default_unit: "",
  test_method: "",
  default_specification: "",
  abbreviations: "",
  description: "",
})

export function LabTestTypeBulkImport() {
  const [data, setData] = useState<LabTestTypeGridRow[]>([createEmptyRow()])
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null)
  const [editValue, setEditValue] = useState("")

  const bulkImportMutation = useBulkImportLabTestTypes()

  const editableColumns = [
    "test_name",
    "test_category",
    "default_unit",
    "test_method",
    "default_specification",
    "abbreviations",
    "description",
  ]

  // Handle cell value updates
  const updateCellValue = useCallback(
    (rowId: string, columnId: string, value: any) => {
      setData((prev) =>
        prev.map((row) => (row.id === rowId ? { ...row, [columnId]: value } : row))
      )
    },
    []
  )

  // Handle keyboard navigation
  const handleCellKeyDown = useCallback(
    (
      e: React.KeyboardEvent,
      rowIndex: number,
      columnId: string,
      saveAndExit?: () => void
    ) => {
      const columnIndex = editableColumns.indexOf(columnId)

      if (e.key === "Tab") {
        e.preventDefault()

        if (saveAndExit) {
          saveAndExit()
        }

        const totalRows = data.length
        const totalCols = editableColumns.length

        let newRowIndex = rowIndex
        let newColIndex = columnIndex

        if (e.shiftKey) {
          newColIndex--
          if (newColIndex < 0) {
            newColIndex = totalCols - 1
            newRowIndex--
            if (newRowIndex < 0) {
              newRowIndex = totalRows - 1
            }
          }
        } else {
          newColIndex++
          if (newColIndex >= totalCols) {
            newColIndex = 0
            newRowIndex++
            if (newRowIndex >= totalRows) {
              newRowIndex = 0
            }
          }
        }

        setTimeout(() => {
          const nextCell = document.querySelector(
            `[data-row-index="${newRowIndex}"][data-col-index="${newColIndex}"]`
          ) as HTMLElement
          if (nextCell) {
            nextCell.focus()
          }
        }, 10)
      } else if (e.key === "Enter") {
        e.preventDefault()
        const row = data[rowIndex]
        setEditingCell({ rowId: row.id, columnId })
        setEditValue(String((row as any)[columnId] || ""))
      }
    },
    [data, editableColumns]
  )

  // Column definitions
  const columnHelper = createColumnHelper<LabTestTypeGridRow>()

  const columns = useMemo<ColumnDef<LabTestTypeGridRow>[]>(
    () => [
      // Checkbox column
      columnHelper.display({
        id: "select",
        header: ({ table }) => (
          <input
            type="checkbox"
            checked={table.getIsAllRowsSelected()}
            onChange={table.getToggleAllRowsSelectedHandler()}
            className="rounded border-slate-300"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            className="rounded border-slate-300"
          />
        ),
        size: 50,
      }),

      // Test Name
      columnHelper.accessor("test_name", {
        header: "Test Name *",
        cell: createEditableCell(
          "test_name",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., Total Plate Count"
        ),
        size: 200,
      }),

      // Test Category (dropdown)
      columnHelper.accessor("test_category", {
        header: "Category *",
        cell: (info) => {
          const rowIndex = info.row.index
          const colIndex = editableColumns.indexOf("test_category")
          const isEditing =
            editingCell?.rowId === info.row.original.id &&
            editingCell?.columnId === "test_category"

          const saveAndExit = () => {
            updateCellValue(info.row.original.id, "test_category", editValue)
            setEditingCell(null)
          }

          if (isEditing) {
            return (
              <select
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={saveAndExit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    saveAndExit()
                  } else if (e.key === "Tab") {
                    handleCellKeyDown(e, rowIndex, "test_category", saveAndExit)
                  } else if (e.key === "Escape") {
                    setEditingCell(null)
                  }
                }}
                autoFocus
                className="w-full h-8 border border-blue-500 rounded px-2 text-sm"
              >
                <option value="">Select...</option>
                {TEST_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            )
          }

          const hasError = info.row.original._errors?.some((err) =>
            err.toLowerCase().includes("test_category")
          )

          return (
            <div
              tabIndex={0}
              data-row-index={rowIndex}
              data-col-index={colIndex}
              onClick={() => {
                setEditingCell({
                  rowId: info.row.original.id,
                  columnId: "test_category",
                })
                setEditValue(info.getValue() || "")
              }}
              onKeyDown={(e) => handleCellKeyDown(e, rowIndex, "test_category")}
              className={`cursor-pointer hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-blue-50 px-2 py-1 rounded min-h-[32px] flex items-center ${
                hasError ? "border-2 border-red-400 bg-red-50" : ""
              }`}
            >
              {info.getValue() || (
                <span className="text-slate-400 italic">Select category</span>
              )}
            </div>
          )
        },
        size: 150,
      }),

      // Default Unit
      columnHelper.accessor("default_unit", {
        header: "Unit",
        cell: createEditableCell(
          "default_unit",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., CFU/g"
        ),
        size: 100,
      }),

      // Test Method
      columnHelper.accessor("test_method", {
        header: "Method",
        cell: createEditableCell(
          "test_method",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., AOAC 990.12"
        ),
        size: 150,
      }),

      // Default Specification
      columnHelper.accessor("default_specification", {
        header: "Spec",
        cell: createEditableCell(
          "default_specification",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., < 10,000"
        ),
        size: 120,
      }),

      // Abbreviations
      columnHelper.accessor("abbreviations", {
        header: "Abbrev",
        cell: createEditableCell(
          "abbreviations",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., TPC"
        ),
        size: 100,
      }),

      // Description
      columnHelper.accessor("description", {
        header: "Description",
        cell: createEditableCell(
          "description",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "Optional notes"
        ),
        size: 200,
      }),
    ],
    [
      columnHelper,
      editableColumns,
      editingCell,
      editValue,
      updateCellValue,
      handleCellKeyDown,
    ]
  )

  // Export template handler
  const handleExportTemplate = useCallback(() => {
    exportTemplate(
      [
        "Test Name",
        "Test Category",
        "Default Unit",
        "Test Method",
        "Default Specification",
        "Abbreviations",
        "Description",
      ],
      "lab-test-types-template"
    )
  }, [])

  // Import file handler
  const handleImportFile = useCallback(async (file: File) => {
    try {
      const rows = await parseExcelFile<LabTestTypeGridRow>(
        file,
        {
          "Test Name": "test_name",
          "Test Category": "test_category",
          "Default Unit": "default_unit",
          "Test Method": "test_method",
          "Default Specification": "default_specification",
          Abbreviations: "abbreviations",
          Description: "description",
        },
        {
          default_unit: "",
          test_method: "",
          default_specification: "",
          abbreviations: "",
          description: "",
        }
      )
      setData(rows)
    } catch (error) {
      console.error("Import failed:", error)
    }
  }, [])

  // Submit handler
  const handleSubmit = useCallback(
    async (
      validRows: Omit<LabTestTypeGridRow, "id" | "_errors" | "_rowError">[]
    ) => {
      await bulkImportMutation.mutateAsync(validRows)
    },
    [bulkImportMutation]
  )

  return (
    <BulkImportGrid
      data={data}
      setData={setData}
      columns={columns}
      editableColumns={editableColumns}
      schema={labTestTypeGridSchema}
      validateRow={(row) => validateRowSchema(labTestTypeGridSchema, row)}
      onSubmit={handleSubmit}
      onExportTemplate={handleExportTemplate}
      onImportFile={handleImportFile}
      title="Bulk Import Lab Test Types"
      submitButtonText="Import Tests"
      templateFilename="lab-test-types-template"
      isSubmitting={bulkImportMutation.isPending}
      createEmptyRow={createEmptyRow}
    />
  )
}
