import { useState, useMemo, useCallback, useRef, useImperativeHandle, forwardRef } from "react"
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table"
import { Loader2, Asterisk } from "lucide-react"
import { cn } from "@/lib/utils"
import { SmartResultInput } from "./SmartResultInput"
import { PassFailBadge } from "./PassFailBadge"
import type { TestResultRow, TestSpecInProduct } from "@/types"

interface EditingCell {
  rowId: number
  columnId: string
}

// Editable columns in tab order
const EDITABLE_COLUMNS = ["result_value", "method", "notes"] as const
type EditableColumn = typeof EDITABLE_COLUMNS[number]

interface TestResultsTableProps {
  /** Test result rows with validation state */
  testResults: TestResultRow[]
  /** Product specifications (for reference) - reserved for future use */
  productSpecs: TestSpecInProduct[]
  /** Callback when a result is updated */
  onUpdateResult: (id: number, field: string, value: string) => Promise<void>
  /** Whether updates are in progress - reserved for future use */
  isUpdating?: boolean
  /** Whether the table is disabled (read-only) */
  disabled?: boolean
  /** ID of the row currently being saved */
  savingRowId?: number | null
  /** Ref to the save button for focus on last cell Tab */
  saveButtonRef?: React.RefObject<HTMLButtonElement | null>
}

export interface TestResultsTableHandle {
  /** Check if there are unsaved changes */
  hasUnsavedChanges: () => boolean
  /** Get current editing state */
  isEditing: () => boolean
}

const columnHelper = createColumnHelper<TestResultRow>()

/**
 * TanStack React Table for test results with inline editing.
 * Columns: Test Type(*) | Category | Spec | Result | Unit | Method | Notes | Pass/Fail
 *
 * Tab navigation: Result → Method → Notes → next row's Result
 * Enter: Save and move down to same column in next row
 * Save on row exit (not on every cell change)
 */
export const TestResultsTable = forwardRef<TestResultsTableHandle, TestResultsTableProps>(
  function TestResultsTable(
    {
      testResults,
      productSpecs: _productSpecs,
      onUpdateResult,
      isUpdating: _isUpdating = false,
      disabled = false,
      savingRowId,
      saveButtonRef,
    },
    ref
  ) {
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null)

  // Refs for cell navigation
  const cellRefs = useRef<Map<string, HTMLElement>>(new Map())

  // Expose methods to parent
  useImperativeHandle(ref, () => ({
    hasUnsavedChanges: () => false, // With immediate save, no pending changes
    isEditing: () => editingCell !== null,
  }))

  // Navigate to a specific cell
  const navigateToCell = useCallback((rowIndex: number, columnId: EditableColumn) => {
    const row = testResults[rowIndex]
    if (!row) return false

    // Use timeout to allow current cell to finish
    setTimeout(() => {
      setEditingCell({ rowId: row.id, columnId })
      // Focus the cell element
      const key = `${row.id}-${columnId}`
      const element = cellRefs.current.get(key)
      if (element) {
        element.focus()
      }
    }, 0)
    return true
  }, [testResults])

  // Handle Tab navigation
  const handleTabNavigation = useCallback((
    currentRowId: number,
    currentColumn: EditableColumn,
    isShiftTab: boolean
  ) => {
    const currentRowIndex = testResults.findIndex(r => r.id === currentRowId)
    if (currentRowIndex === -1) return

    const currentColIndex = EDITABLE_COLUMNS.indexOf(currentColumn)

    let nextRowIndex = currentRowIndex
    let nextColIndex = currentColIndex

    if (isShiftTab) {
      // Move backwards
      nextColIndex--
      if (nextColIndex < 0) {
        nextColIndex = EDITABLE_COLUMNS.length - 1
        nextRowIndex--
      }
    } else {
      // Move forwards
      nextColIndex++
      if (nextColIndex >= EDITABLE_COLUMNS.length) {
        nextColIndex = 0
        nextRowIndex++
      }
    }

    // Check bounds
    if (nextRowIndex < 0) {
      // At beginning, stay on first cell
      return
    }

    if (nextRowIndex >= testResults.length) {
      // At end, focus save button
      setEditingCell(null)
      saveButtonRef?.current?.focus()
      return
    }

    navigateToCell(nextRowIndex, EDITABLE_COLUMNS[nextColIndex])
  }, [testResults, navigateToCell, saveButtonRef])

  // Handle Enter navigation (move down to same column)
  const handleEnterNavigation = useCallback((
    currentRowId: number,
    currentColumn: EditableColumn
  ) => {
    const currentRowIndex = testResults.findIndex(r => r.id === currentRowId)
    if (currentRowIndex === -1) return

    const nextRowIndex = currentRowIndex + 1

    if (nextRowIndex >= testResults.length) {
      // At last row, just end editing
      setEditingCell(null)
      return
    }

    navigateToCell(nextRowIndex, currentColumn)
  }, [testResults, navigateToCell])

  // Handle update - save immediately
  const handleCellChange = useCallback((rowId: number, field: string, value: string) => {
    onUpdateResult(rowId, field, value)
  }, [onUpdateResult])

  // Start editing a cell
  const startEdit = useCallback((rowId: number, columnId: string) => {
    if (disabled) return
    setEditingCell({ rowId, columnId })
  }, [disabled])

  // End editing
  const endEdit = useCallback(() => {
    setEditingCell(null)
  }, [])

  // Define columns
  const columns = useMemo(
    () => [
      // Test Type - read only, with asterisk for required
      columnHelper.accessor("test_type", {
        header: "Test Type",
        size: 180,
        cell: (info) => {
          const row = info.row.original
          const isRequired = row.specificationObj?.is_required ?? false
          return (
            <div className="flex items-center gap-1">
              <span className="font-medium text-slate-900">{info.getValue()}</span>
              {isRequired && (
                <Asterisk className="h-3 w-3 text-red-500" aria-label="Required" />
              )}
            </div>
          )
        },
      }),

      // Category - read only
      columnHelper.accessor((row) => row.specificationObj?.test_category, {
        id: "category",
        header: "Category",
        size: 100,
        cell: (info) => (
          <span className="text-slate-600 text-xs">{info.getValue() || "—"}</span>
        ),
      }),

      // Spec - read only
      columnHelper.accessor("specification", {
        header: "Spec",
        size: 100,
        cell: (info) => (
          <span className="text-slate-600 font-mono text-xs">
            {info.getValue() || "—"}
          </span>
        ),
      }),

      // Result - editable with smart input
      columnHelper.accessor("result_value", {
        header: "Result",
        size: 140,
        cell: (info) => {
          const row = info.row.original
          const isEditing =
            editingCell?.rowId === row.id && editingCell?.columnId === "result_value"
          const isSaving = savingRowId === row.id

          return (
            <div
              className="relative"
              ref={(el) => {
                if (el) cellRefs.current.set(`${row.id}-result_value`, el)
              }}
            >
              <SmartResultInput
                value={row.result_value || ""}
                specification={row.specification || ""}
                testUnit={row.unit}
                isEditing={isEditing}
                disabled={disabled || isSaving}
                onStartEdit={() => startEdit(row.id, "result_value")}
                onEndEdit={endEdit}
                onChange={(value) => handleCellChange(row.id, "result_value", value)}
                onTab={(isShift) => handleTabNavigation(row.id, "result_value", isShift)}
                onEnter={() => handleEnterNavigation(row.id, "result_value")}
              />
              {isSaving && (
                <Loader2 className="absolute right-1 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-blue-500" />
              )}
            </div>
          )
        },
      }),

      // Unit - read only (from spec)
      columnHelper.accessor("unit", {
        header: "Unit",
        size: 80,
        cell: (info) => (
          <span className="text-slate-500 text-xs">{info.getValue() || "—"}</span>
        ),
      }),

      // Method - editable
      columnHelper.accessor("method", {
        header: "Method",
        size: 120,
        cell: (info) => {
          const row = info.row.original
          const isEditing =
            editingCell?.rowId === row.id && editingCell?.columnId === "method"

          if (disabled) {
            return (
              <span className="text-slate-600 text-xs">{info.getValue() || "—"}</span>
            )
          }

          if (!isEditing) {
            return (
              <div
                onClick={() => startEdit(row.id, "method")}
                className="min-h-[32px] px-2 py-1 rounded cursor-text hover:bg-slate-50 flex items-center"
                tabIndex={0}
                ref={(el) => {
                  if (el) cellRefs.current.set(`${row.id}-method`, el)
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    startEdit(row.id, "method")
                  }
                }}
              >
                {info.getValue() ? (
                  <span className="text-slate-600 text-xs">{info.getValue()}</span>
                ) : (
                  <span className="text-slate-400 text-xs italic">—</span>
                )}
              </div>
            )
          }

          return (
            <input
              type="text"
              autoFocus
              defaultValue={info.getValue() || ""}
              onBlur={(e) => {
                handleCellChange(row.id, "method", e.target.value)
                endEdit()
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") endEdit()
                if (e.key === "Tab") {
                  e.preventDefault()
                  handleCellChange(row.id, "method", e.currentTarget.value)
                  handleTabNavigation(row.id, "method", e.shiftKey)
                }
                if (e.key === "Enter") {
                  e.preventDefault()
                  handleCellChange(row.id, "method", e.currentTarget.value)
                  handleEnterNavigation(row.id, "method")
                }
              }}
              className="h-8 w-full px-2 text-xs border border-blue-500 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          )
        },
      }),

      // Notes - editable
      columnHelper.accessor("notes", {
        header: "Notes",
        size: 150,
        cell: (info) => {
          const row = info.row.original
          const isEditing =
            editingCell?.rowId === row.id && editingCell?.columnId === "notes"

          if (disabled) {
            return (
              <span className="text-slate-600 text-xs">{info.getValue() || "—"}</span>
            )
          }

          if (!isEditing) {
            return (
              <div
                onClick={() => startEdit(row.id, "notes")}
                className="min-h-[32px] px-2 py-1 rounded cursor-text hover:bg-slate-50 flex items-center"
                tabIndex={0}
                ref={(el) => {
                  if (el) cellRefs.current.set(`${row.id}-notes`, el)
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    startEdit(row.id, "notes")
                  }
                }}
              >
                {info.getValue() ? (
                  <span className="text-slate-600 text-xs truncate max-w-[130px]">
                    {info.getValue()}
                  </span>
                ) : (
                  <span className="text-slate-400 text-xs italic">—</span>
                )}
              </div>
            )
          }

          return (
            <input
              type="text"
              autoFocus
              defaultValue={info.getValue() || ""}
              onBlur={(e) => {
                handleCellChange(row.id, "notes", e.target.value)
                endEdit()
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") endEdit()
                if (e.key === "Tab") {
                  e.preventDefault()
                  handleCellChange(row.id, "notes", e.currentTarget.value)
                  handleTabNavigation(row.id, "notes", e.shiftKey)
                }
                if (e.key === "Enter") {
                  e.preventDefault()
                  handleCellChange(row.id, "notes", e.currentTarget.value)
                  handleEnterNavigation(row.id, "notes")
                }
              }}
              className="h-8 w-full px-2 text-xs border border-blue-500 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          )
        },
      }),

      // Pass/Fail - read only, computed
      columnHelper.accessor("passFailStatus", {
        header: "Pass/Fail",
        size: 100,
        cell: (info) => {
          // Convert 'pending' to null for PassFailBadge
          const status = info.getValue()
          const badgeStatus = status === 'pending' ? null : status
          return (
            <PassFailBadge
              status={badgeStatus}
              isFlagged={info.row.original.isFlagged}
            />
          )
        },
      }),
    ],
    [editingCell, disabled, startEdit, endEdit, handleCellChange, handleTabNavigation, handleEnterNavigation, savingRowId]
  )

  const table = useReactTable({
    data: testResults,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id.toString(),
  })

  if (testResults.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 py-8 text-center">
        <p className="text-sm text-slate-500">No test results</p>
        <p className="mt-1 text-xs text-slate-400">
          Tests will appear here based on product specifications
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="border-b border-slate-200 bg-slate-50">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    style={{ width: header.getSize() }}
                    className="text-left font-semibold text-slate-700 text-xs tracking-wide px-3 py-2 uppercase"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-slate-100 hover:bg-slate-50/50 transition-colors",
                  row.original.isFlagged && "bg-red-50/50"
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    style={{ width: cell.column.getSize() }}
                    className="px-3 py-2"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
})
