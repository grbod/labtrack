import { useState, useMemo, useCallback, useRef, useImperativeHandle, forwardRef, useEffect } from "react"
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

// Editable columns in tab order (Result → Notes, skip Method since it's from spec)
const EDITABLE_COLUMNS = ["result_value", "notes"] as const
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
  /** Map of test_result_id -> original_value for retested tests */
  originalValuesMap?: Map<number, string | null>
  /** Callback when navigation should move outside the table */
  onRequestNextFocus?: (direction: "forward" | "backward") => void
}

export interface TestResultsTableHandle {
  /** Check if there are unsaved changes */
  hasUnsavedChanges: () => boolean
  /** Get current editing state */
  isEditing: () => boolean
  /** Focus the first editable cell */
  focusFirstCell: () => void
  /** Focus the last editable cell */
  focusLastCell: () => void
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
      originalValuesMap,
      onRequestNextFocus,
    },
    ref
  ) {
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null)

  // Refs for input elements (set when in editing mode)
  const inputRefs = useRef<Map<string, HTMLInputElement | HTMLSelectElement>>(new Map())

  // Track pending tab navigation - when set, endEdit should navigate to this cell instead of clearing
  const pendingTabNavigation = useRef<EditingCell | null>(null)

  // Expose methods to parent
  useImperativeHandle(
    ref,
    () => ({
      hasUnsavedChanges: () => false, // With immediate save, no pending changes
      isEditing: () => editingCell !== null,
      focusFirstCell: () => {
        if (!testResults.length) return
        setEditingCell({ rowId: testResults[0].id, columnId: "result_value" })
      },
      focusLastCell: () => {
        if (!testResults.length) return
        setEditingCell({ rowId: testResults[testResults.length - 1].id, columnId: "notes" })
      },
    }),
    [editingCell, testResults]
  )

  // Focus input when editingCell changes
  useEffect(() => {
    if (editingCell) {
      // Use requestAnimationFrame to wait for render, then focus
      requestAnimationFrame(() => {
        const key = `${editingCell.rowId}-${editingCell.columnId}`
        const input = inputRefs.current.get(key)
        if (input) {
          input.focus()
          if ('select' in input && typeof input.select === 'function') {
            input.select()
          }
        }
      })
    }
  }, [editingCell])

  // CRITICAL: Intercept Tab in CAPTURE phase on WINDOW - runs BEFORE Radix Dialog focus trap
  // Radix's focus trap listens on document capture phase, but window capture runs first
  useEffect(() => {
    const handleTabCapture = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      // Check if active element is one of our tracked inputs
      const activeEl = document.activeElement
      let currentRowId: number | null = null
      let currentColumnId: EditableColumn | null = null

      // Find which of our inputs is focused
      for (const [key, input] of inputRefs.current.entries()) {
        if (input === activeEl) {
          const dashIndex = key.indexOf('-')
          const rowIdStr = key.substring(0, dashIndex)
          const colId = key.substring(dashIndex + 1) as EditableColumn
          currentRowId = parseInt(rowIdStr, 10)
          currentColumnId = colId
          break
        }
      }

      // Not our input - let Radix handle it normally
      if (currentRowId === null || currentColumnId === null) return

      // KILL the event before Radix focus trap sees it
      e.stopImmediatePropagation()
      e.preventDefault()

      // Calculate next cell
      const currentRowIndex = testResults.findIndex(r => r.id === currentRowId)
      if (currentRowIndex === -1) return

      const currentColIndex = EDITABLE_COLUMNS.indexOf(currentColumnId)
      let nextRowIndex = currentRowIndex
      let nextColIndex = currentColIndex

      if (e.shiftKey) {
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

      const direction: "forward" | "backward" = e.shiftKey ? "backward" : "forward"

      // Check bounds
      if (nextRowIndex < 0) {
        pendingTabNavigation.current = null
        if (activeEl instanceof HTMLElement) {
          activeEl.blur()
        }
        setTimeout(() => {
          if (onRequestNextFocus) {
            onRequestNextFocus("backward")
          } else {
            saveButtonRef?.current?.focus()
          }
        }, 0)
        return
      }

      if (nextRowIndex >= testResults.length) {
        pendingTabNavigation.current = null
        // Blur the current input to trigger save, then focus save button
        if (activeEl instanceof HTMLElement) {
          activeEl.blur()
        }
        // Use setTimeout to focus save button after blur handler runs
        setTimeout(() => {
          if (onRequestNextFocus) {
            onRequestNextFocus(direction)
          } else {
            saveButtonRef?.current?.focus()
          }
        }, 0)
        return
      }

      // Set pending navigation - endEdit will navigate to this cell when blur handler calls it
      const nextRow = testResults[nextRowIndex]
      pendingTabNavigation.current = { rowId: nextRow.id, columnId: EDITABLE_COLUMNS[nextColIndex] }

      // Blur the current input - this triggers the blur handler which calls onChange and endEdit
      // The endEdit will see pendingTabNavigation and navigate to the next cell
      if (activeEl instanceof HTMLElement) {
        activeEl.blur()
      }
    }

    // Add listener on WINDOW with CAPTURE phase - runs before document-level Radix listener
    window.addEventListener('keydown', handleTabCapture, { capture: true })
    return () => window.removeEventListener('keydown', handleTabCapture, { capture: true })
  }, [testResults, saveButtonRef, onRequestNextFocus])

  // Navigate to a specific cell
  const navigateToCell = useCallback((rowIndex: number, columnId: EditableColumn) => {
    const row = testResults[rowIndex]
    if (!row) return false

    setEditingCell({ rowId: row.id, columnId })
    return true
  }, [testResults])

  // Handle Tab navigation - navigates IMMEDIATELY to override blur's setEditingCell(null)
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
      setEditingCell(null)
      if (onRequestNextFocus) {
        onRequestNextFocus("backward")
      } else {
        saveButtonRef?.current?.focus()
      }
      return
    }

    if (nextRowIndex >= testResults.length) {
      setEditingCell(null)
      if (onRequestNextFocus) {
        onRequestNextFocus("forward")
      } else {
        saveButtonRef?.current?.focus()
      }
      return
    }

    // Navigate IMMEDIATELY - React batches this with blur's setEditingCell(null)
    // Our call comes later in the event, so it wins
    const nextRow = testResults[nextRowIndex]
    setEditingCell({ rowId: nextRow.id, columnId: EDITABLE_COLUMNS[nextColIndex] })
  }, [testResults, saveButtonRef, onRequestNextFocus])

  // Handle Enter navigation (move down to same column) - navigates immediately
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

    // Navigate IMMEDIATELY
    const nextRow = testResults[nextRowIndex]
    setEditingCell({ rowId: nextRow.id, columnId: currentColumn })
  }, [testResults])

  // Handle update - save immediately
  const handleCellChange = useCallback((rowId: number, field: string, value: string) => {
    onUpdateResult(rowId, field, value)
  }, [onUpdateResult])

  // Start editing a cell
  const startEdit = useCallback((rowId: number, columnId: string) => {
    if (disabled) return
    setEditingCell({ rowId, columnId })
  }, [disabled])

  // End editing - but check if we have pending tab navigation
  const endEdit = useCallback(() => {
    if (pendingTabNavigation.current) {
      // Tab navigation is pending - navigate to next cell instead of clearing
      setEditingCell(pendingTabNavigation.current)
      pendingTabNavigation.current = null
    } else {
      setEditingCell(null)
    }
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

          // Check if this test has been retested (has original value)
          const originalValue = originalValuesMap?.get(row.id)
          const hasBeenRetested = originalValue !== undefined && originalValue !== row.result_value

          return (
            <div className="relative">
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
                onInputRef={(el) => {
                  if (el) {
                    inputRefs.current.set(`${row.id}-result_value`, el)
                  }
                }}
              />
              {/* Show original value if test was retested */}
              {hasBeenRetested && (
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Original: {originalValue || "—"}
                </div>
              )}
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
              ref={(el) => {
                if (el) inputRefs.current.set(`${row.id}-method`, el)
              }}
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
                  e.stopPropagation() // Prevent Radix Dialog focus trap from intercepting
                  handleCellChange(row.id, "method", e.currentTarget.value)
                  // Method is not in tab order - go to Notes (forward) or Result (backward) in same row
                  const currentRowIndex = testResults.findIndex(r => r.id === row.id)
                  if (e.shiftKey) {
                    navigateToCell(currentRowIndex, "result_value")
                  } else {
                    navigateToCell(currentRowIndex, "notes")
                  }
                }
                if (e.key === "Enter") {
                  e.preventDefault()
                  handleCellChange(row.id, "method", e.currentTarget.value)
                  endEdit()
                }
              }}
              className="h-8 w-full px-2 text-xs border border-blue-500 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          )
        },
      }),

      // Reason - editable (for explaining pass/fail decisions)
      columnHelper.accessor("notes", {
        header: "Reason",
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
              ref={(el) => {
                if (el) inputRefs.current.set(`${row.id}-notes`, el)
              }}
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
                  e.stopPropagation() // Prevent Radix Dialog focus trap from intercepting
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
    [editingCell, disabled, startEdit, endEdit, handleCellChange, handleTabNavigation, handleEnterNavigation, savingRowId, testResults, navigateToCell, inputRefs]
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
