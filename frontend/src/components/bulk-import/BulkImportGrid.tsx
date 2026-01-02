import { useState, useCallback, useMemo, useRef } from "react"
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
} from "@tanstack/react-table"
import {
  Plus,
  Trash2,
  Upload,
  Download,
  AlertCircle,
  Clipboard,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { BulkImportRow, BulkImportGridProps, EditingCell } from "./types"

export function BulkImportGrid<T extends BulkImportRow>({
  data,
  setData,
  columns,
  editableColumns,
  validateRow,
  onSubmit,
  onExportTemplate,
  onImportFile,
  title,
  submitButtonText = "Import",
  isSubmitting = false,
  createEmptyRow,
}: BulkImportGridProps<T>) {
  const [pasteReady, setPasteReady] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Validate all rows and count errors
  const validatedData = useMemo(() => {
    return data.map((row) => {
      const { valid, errors } = validateRow(row)
      return {
        ...row,
        _errors: valid ? undefined : errors,
      }
    })
  }, [data, validateRow])

  const validRowCount = validatedData.filter((r) => !r._errors?.length).length
  const errorRowCount = validatedData.filter((r) => r._errors?.length).length

  // TanStack Table instance
  const table = useReactTable({
    data: validatedData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    enableRowSelection: true,
    getRowId: (row) => row.id,
  })

  // Add row handler
  const handleAddRow = useCallback(() => {
    setData((prev) => [...prev, createEmptyRow()])
  }, [setData, createEmptyRow])

  // Delete selected rows
  const handleDeleteSelected = useCallback(() => {
    const selectedRows = table.getSelectedRowModel().rows
    const selectedIds = new Set(selectedRows.map((r) => r.original.id))
    setData((prev) => prev.filter((row) => !selectedIds.has(row.id)))
    table.resetRowSelection()
  }, [table, setData])

  // Handle file import
  const handleFileImport = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) {
        try {
          await onImportFile(file)
        } catch (error) {
          console.error("Import failed:", error)
        }
        // Reset input
        if (fileInputRef.current) {
          fileInputRef.current.value = ""
        }
      }
    },
    [onImportFile]
  )

  // Handle paste from Excel (placeholder - implemented in specific components)
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault()
    // Paste handling is component-specific
    setPasteReady(false)
  }, [])

  // Handle submit
  const handleSubmit = useCallback(async () => {
    const validRows = validatedData
      .filter((row) => !row._errors?.length)
      .map(({ id, _errors, _rowError, ...rest }) => rest as any)

    if (validRows.length === 0) {
      return
    }

    try {
      await onSubmit(validRows)
      // Clear data on success
      setData([createEmptyRow()])
      table.resetRowSelection()
    } catch (error) {
      console.error("Submit failed:", error)
    }
  }, [validatedData, onSubmit, setData, createEmptyRow, table])

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-900">{title}</h3>
          <p className="text-sm text-slate-500 mt-0.5">
            {validRowCount} valid, {errorRowCount} errors
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={onExportTemplate}
            className="h-9"
          >
            <Download className="mr-2 h-4 w-4" />
            Template
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            className="h-9"
          >
            <Upload className="mr-2 h-4 w-4" />
            Import File
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={handleFileImport}
            className="hidden"
          />

          <Button size="sm" variant="outline" onClick={handleAddRow} className="h-9">
            <Plus className="mr-2 h-4 w-4" />
            Add Row
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={handleDeleteSelected}
            disabled={table.getSelectedRowModel().rows.length === 0}
            className="h-9"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete Selected
          </Button>

          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={validRowCount === 0 || isSubmitting}
            className="h-9"
          >
            {isSubmitting ? (
              <>Importing...</>
            ) : (
              <>
                {submitButtonText} ({validRowCount})
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Paste indicator */}
      {pasteReady && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 animate-pulse">
          <Clipboard className="h-4 w-4 text-green-600" />
          <span className="text-sm text-green-800 font-medium">
            ✨ Paste ready! Press Ctrl+V (Cmd+V on Mac) to paste Excel data
          </span>
        </div>
      )}

      {/* Table */}
      <div
        className="rounded-lg border border-slate-200 overflow-hidden bg-white"
        onPaste={handlePaste}
        onFocus={() => setPasteReady(true)}
        onBlur={() => setPasteReady(false)}
        tabIndex={-1}
      >
        <div className="overflow-auto" style={{ maxHeight: 500 }}>
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0 z-10">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-3 py-3 text-left text-xs font-semibold text-slate-700 uppercase tracking-wider"
                      style={{ width: header.getSize() }}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={`hover:bg-slate-50 ${
                    row.original._errors?.length ? "bg-red-50" : ""
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2 text-sm text-slate-900">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Error summary */}
      {errorRowCount > 0 && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-red-900 text-sm">
                {errorRowCount} row{errorRowCount !== 1 ? "s" : ""} with errors
              </p>
              <p className="text-sm text-red-700 mt-1">
                Fix validation errors before importing. Rows with errors are
                highlighted in red.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Factory function to create editable cell renderer
 * Pattern from GridShowcase - makes TanStack Table work like Excel
 */
export function createEditableCell<T extends BulkImportRow>(
  columnId: keyof T,
  editableColumns: string[],
  editingCell: EditingCell | null,
  editValue: string,
  setEditingCell: (cell: EditingCell | null) => void,
  setEditValue: (value: string) => void,
  updateCellValue: (rowId: string, columnId: string, value: any) => void,
  handleCellKeyDown: (
    e: React.KeyboardEvent,
    rowIndex: number,
    columnId: string,
    saveAndExit?: () => void
  ) => void,
  type: "text" | "number" = "text",
  placeholder?: string
) {
  return (info: any) => {
    const rowIndex = info.row.index
    const colIndex = editableColumns.indexOf(columnId as string)
    const isEditing =
      editingCell?.rowId === info.row.original.id &&
      editingCell?.columnId === columnId

    const saveAndExit = () => {
      const finalValue = type === "number" ? parseFloat(editValue) || 0 : editValue
      updateCellValue(info.row.original.id, columnId as string, finalValue)
      setEditingCell(null)
    }

    if (isEditing) {
      return (
        <Input
          type={type}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={saveAndExit}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              saveAndExit()
            } else if (e.key === "Tab") {
              handleCellKeyDown(e, rowIndex, columnId as string, saveAndExit)
            } else if (e.key === "Escape") {
              setEditingCell(null)
            }
          }}
          autoFocus
          className="h-8 border-blue-500"
          placeholder={placeholder}
        />
      )
    }

    const hasError = info.row.original._errors?.some((err: string) =>
      err.toLowerCase().includes(String(columnId).toLowerCase())
    )

    return (
      <div
        tabIndex={0}
        data-row-index={rowIndex}
        data-col-index={colIndex}
        onClick={() => {
          setEditingCell({
            rowId: info.row.original.id,
            columnId: columnId as string,
          })
          setEditValue(String(info.getValue() || ""))
        }}
        onKeyDown={(e) => handleCellKeyDown(e, rowIndex, columnId as string)}
        className={`cursor-text hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-blue-50 px-2 py-1 rounded min-h-[32px] flex items-center ${
          hasError ? "border-2 border-red-400 bg-red-50" : ""
        }`}
      >
        {info.getValue() || (
          <span className="text-slate-400 italic">
            {placeholder || "Click to edit"}
          </span>
        )}
      </div>
    )
  }
}
