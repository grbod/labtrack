import { useState, useCallback, useMemo } from "react"
import { createColumnHelper } from "@tanstack/react-table"
import { nanoid } from "nanoid"
import { BulkImportGrid, createEditableCell } from "./BulkImportGrid"
import { useBulkImportProducts } from "@/hooks/useProducts"
import {
  productGridSchema,
  type ProductGridRow,
  validateRow as validateRowSchema,
} from "@/lib/bulk-import/validators"
import {
  exportTemplate,
  parseExcelFile,
} from "@/lib/bulk-import/excel-utils"
import { generateDisplayName } from "@/lib/product-utils"
import type { EditingCell } from "./types"

const createEmptyRow = (): ProductGridRow => ({
  id: nanoid(),
  brand: "",
  product_name: "",
  flavor: "",
  size: "",
  version: "",
  serving_size: "",
  expiry_duration_months: 36,
})

export function ProductBulkImport() {
  const [data, setData] = useState<ProductGridRow[]>([createEmptyRow()])
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null)
  const [editValue, setEditValue] = useState("")

  const bulkImportMutation = useBulkImportProducts()

  const editableColumns = [
    "brand",
    "product_name",
    "flavor",
    "size",
    "version",
    "serving_size",
    "expiry_duration_months",
  ]

  // Handle cell value updates - also marks row as touched for validation
  const updateCellValue = useCallback(
    (rowId: string, columnId: string, value: any) => {
      setData((prev) =>
        prev.map((row) => (row.id === rowId ? { ...row, [columnId]: value, _touched: true } : row))
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
  const columnHelper = createColumnHelper<ProductGridRow>()

  const columns = useMemo(
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

      // Brand
      columnHelper.accessor("brand", {
        header: "Brand *",
        cell: createEditableCell(
          "brand",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., Truvani"
        ),
        size: 150,
      }),

      // Product Name
      columnHelper.accessor("product_name", {
        header: "Product Name *",
        cell: createEditableCell(
          "product_name",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., Organic Whey Protein"
        ),
        size: 200,
      }),

      // Flavor
      columnHelper.accessor("flavor", {
        header: "Flavor",
        cell: createEditableCell(
          "flavor",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., Vanilla"
        ),
        size: 120,
      }),

      // Size
      columnHelper.accessor("size", {
        header: "Size",
        cell: createEditableCell(
          "size",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., 2 lbs"
        ),
        size: 100,
      }),

      // Version
      columnHelper.accessor("version", {
        header: "Version",
        cell: createEditableCell(
          "version",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., 1, 2"
        ),
        size: 80,
      }),

      // Display Name Preview (computed, read-only)
      columnHelper.display({
        id: "display_name_preview",
        header: "Display Name (Preview)",
        cell: ({ row }) => {
          const preview = generateDisplayName(
            row.original.brand,
            row.original.product_name,
            row.original.flavor,
            row.original.size,
            row.original.version
          )
          return (
            <span className="text-slate-600 text-[13px] italic truncate block" title={preview}>
              {preview || <span className="text-slate-400">Enter brand & product...</span>}
            </span>
          )
        },
        size: 250,
      }),

      // Serving Size
      columnHelper.accessor("serving_size", {
        header: "Serving (g)",
        cell: createEditableCell(
          "serving_size",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "text",
          "e.g., 28.5"
        ),
        size: 120,
      }),

      // Expiry Duration
      columnHelper.accessor("expiry_duration_months", {
        header: "Expiry (mo)",
        cell: createEditableCell(
          "expiry_duration_months",
          editableColumns,
          editingCell,
          editValue,
          setEditingCell,
          setEditValue,
          updateCellValue,
          handleCellKeyDown,
          "number",
          "36"
        ),
        size: 120,
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
        "Brand",
        "Product Name",
        "Flavor",
        "Size",
        "Version",
        "Serving Size",
        "Expiry Duration (months)",
      ],
      "products-template"
    )
  }, [])

  // Handle paste from Excel
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault()
    const text = e.clipboardData.getData('text/plain')
    if (!text.trim()) return

    // Template column order: Brand, Product Name, Flavor, Size, Version, Serving Size, Expiry
    const columnOrder = ['brand', 'product_name', 'flavor', 'size', 'version', 'serving_size', 'expiry_duration_months'] as const

    const lines = text.trim().split('\n')
    const newRows = lines.map(line => {
      const cells = line.split('\t')
      const row = createEmptyRow()
      columnOrder.forEach((col, idx) => {
        if (cells[idx] !== undefined && cells[idx].trim() !== '') {
          if (col === 'expiry_duration_months') {
            (row as any)[col] = parseInt(cells[idx]) || 36
          } else {
            (row as any)[col] = cells[idx].trim()
          }
        }
      })
      // Mark pasted rows as touched so they get validated
      row._touched = true
      return row
    })

    // Replace empty rows with pasted data
    setData(prev => {
      const nonEmpty = prev.filter(r => r.brand || r.product_name)
      return [...nonEmpty, ...newRows]
    })
  }, [setData])

  // Import file handler
  const handleImportFile = useCallback(async (file: File) => {
    try {
      const rows = await parseExcelFile<ProductGridRow>(
        file,
        {
          Brand: "brand",
          "Product Name": "product_name",
          Flavor: "flavor",
          Size: "size",
          Version: "version",
          "Serving Size": "serving_size",
          "Expiry Duration (months)": "expiry_duration_months",
        },
        {
          flavor: "",
          size: "",
          version: "",
          serving_size: "",
          expiry_duration_months: 36,
        }
      )
      // Mark imported rows as touched so they get validated
      setData(rows.map(row => ({ ...row, _touched: true })))
    } catch (error) {
      console.error("Import failed:", error)
    }
  }, [])

  // Submit handler - generates display_name before sending to API
  const handleSubmit = useCallback(
    async (validRows: Omit<ProductGridRow, "id" | "_errors" | "_rowError">[]) => {
      // Transform rows to include generated display_name
      const rowsWithDisplayName = validRows.map(row => ({
        brand: row.brand,
        product_name: row.product_name,
        flavor: row.flavor || undefined,
        size: row.size || undefined,
        serving_size: row.serving_size || undefined,
        expiry_duration_months: row.expiry_duration_months,
        // Generate display_name from fields
        display_name: generateDisplayName(
          row.brand,
          row.product_name,
          row.flavor,
          row.size,
          row.version
        ),
      }))
      await bulkImportMutation.mutateAsync(rowsWithDisplayName)
    },
    [bulkImportMutation]
  )

  return (
    <BulkImportGrid
      data={data}
      setData={setData}
      columns={columns}
      editableColumns={editableColumns}
      schema={productGridSchema}
      validateRow={(row) => validateRowSchema(productGridSchema, row)}
      onSubmit={handleSubmit}
      onExportTemplate={handleExportTemplate}
      onImportFile={handleImportFile}
      onPaste={handlePaste}
      title="Bulk Import Products"
      submitButtonText="Import Products"
      templateFilename="products-template"
      isSubmitting={bulkImportMutation.isPending}
      createEmptyRow={createEmptyRow}
    />
  )
}
