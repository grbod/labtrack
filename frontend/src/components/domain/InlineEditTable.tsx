import { useState, useCallback, useRef, useEffect } from "react"
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Check, Circle, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { TestResult } from "@/types"

// Editable columns in order for Tab navigation - defined outside component
const EDITABLE_FIELDS = ["result_value", "unit", "method", "notes"] as const
type EditableField = (typeof EDITABLE_FIELDS)[number]

interface EditingCell {
  resultId: number
  field: EditableField
}

interface InlineEditTableProps {
  testResults: TestResult[]
  onUpdateResult: (id: number, field: string, value: string) => Promise<void>
  isUpdating?: boolean
  disabled?: boolean
}

/**
 * Spreadsheet-style inline editable table for test results.
 * Click any cell to edit, Tab/Enter to navigate, ESC to cancel.
 */
export function InlineEditTable({
  testResults,
  onUpdateResult,
  isUpdating = false,
  disabled = false,
}: InlineEditTableProps) {
  const [editingCell, setEditingCell] = useState<EditingCell | null>(null)
  const [editValue, setEditValue] = useState("")
  const [pendingCell, setPendingCell] = useState<EditingCell | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Focus input when editing starts
  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editingCell])

  // Start editing a cell
  const startEdit = useCallback(
    (result: TestResult, field: EditingCell["field"]) => {
      if (disabled) return

      setEditingCell({ resultId: result.id, field })
      setEditValue(String(result[field] || ""))
    },
    [disabled]
  )

  // Save current edit and optionally move to next cell
  const saveAndNavigate = useCallback(
    async (direction?: "next" | "prev" | "down" | "up") => {
      if (!editingCell) return

      const currentResult = testResults.find((r) => r.id === editingCell.resultId)
      if (!currentResult) return

      const originalValue = String(currentResult[editingCell.field] || "")

      // Only save if value changed
      if (editValue !== originalValue) {
        setPendingCell(editingCell)
        try {
          await onUpdateResult(editingCell.resultId, editingCell.field, editValue)
        } catch (error) {
          console.error("Failed to update:", error)
        } finally {
          setPendingCell(null)
        }
      }

      // Calculate next cell
      if (direction) {
        const currentRowIndex = testResults.findIndex((r) => r.id === editingCell.resultId)
        const currentColIndex = EDITABLE_FIELDS.indexOf(editingCell.field)

        let nextRowIndex = currentRowIndex
        let nextColIndex = currentColIndex

        switch (direction) {
          case "next":
            nextColIndex++
            if (nextColIndex >= EDITABLE_FIELDS.length) {
              nextColIndex = 0
              nextRowIndex++
            }
            break
          case "prev":
            nextColIndex--
            if (nextColIndex < 0) {
              nextColIndex = EDITABLE_FIELDS.length - 1
              nextRowIndex--
            }
            break
          case "down":
            nextRowIndex++
            break
          case "up":
            nextRowIndex--
            break
        }

        // Wrap around
        if (nextRowIndex >= testResults.length) nextRowIndex = 0
        if (nextRowIndex < 0) nextRowIndex = testResults.length - 1

        const nextResult = testResults[nextRowIndex]
        if (nextResult) {
          setEditingCell({
            resultId: nextResult.id,
            field: EDITABLE_FIELDS[nextColIndex],
          })
          setEditValue(String(nextResult[EDITABLE_FIELDS[nextColIndex]] || ""))
        }
      } else {
        setEditingCell(null)
      }
    },
    [editingCell, editValue, testResults, onUpdateResult]
  )

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case "Tab":
          e.preventDefault()
          saveAndNavigate(e.shiftKey ? "prev" : "next")
          break
        case "Enter":
          e.preventDefault()
          saveAndNavigate("down")
          break
        case "Escape":
          e.preventDefault()
          setEditingCell(null)
          break
        case "ArrowDown":
          if (e.altKey) {
            e.preventDefault()
            saveAndNavigate("down")
          }
          break
        case "ArrowUp":
          if (e.altKey) {
            e.preventDefault()
            saveAndNavigate("up")
          }
          break
      }
    },
    [saveAndNavigate]
  )

  // Render a cell - either editing or display mode
  const renderCell = (
    result: TestResult,
    field: EditingCell["field"],
    placeholder: string
  ) => {
    const isEditing =
      editingCell?.resultId === result.id && editingCell?.field === field
    const isPending =
      pendingCell?.resultId === result.id && pendingCell?.field === field
    const value = result[field]

    if (isEditing) {
      return (
        <Input
          ref={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={() => saveAndNavigate()}
          onKeyDown={handleKeyDown}
          className="h-8 text-sm border-blue-500 focus-visible:ring-blue-500"
          placeholder={placeholder}
          disabled={isUpdating}
        />
      )
    }

    return (
      <div
        onClick={() => startEdit(result, field)}
        className={cn(
          "min-h-[32px] px-2 py-1 rounded cursor-text flex items-center",
          "hover:bg-slate-50 transition-colors",
          disabled
            ? "cursor-not-allowed opacity-60"
            : "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-blue-50"
        )}
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            startEdit(result, field)
          }
        }}
      >
        {isPending ? (
          <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
        ) : value ? (
          <span className="text-sm text-slate-900">{value}</span>
        ) : (
          <span className="text-sm text-slate-400 italic">{placeholder}</span>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-slate-50">
            <TableHead className="text-xs font-semibold text-slate-600 w-[180px]">
              Test Type
            </TableHead>
            <TableHead className="text-xs font-semibold text-slate-600 w-[140px]">
              Result
            </TableHead>
            <TableHead className="text-xs font-semibold text-slate-600 w-[80px]">
              Unit
            </TableHead>
            <TableHead className="text-xs font-semibold text-slate-600 w-[120px]">
              Spec
            </TableHead>
            <TableHead className="text-xs font-semibold text-slate-600 w-[140px]">
              Method
            </TableHead>
            <TableHead className="text-xs font-semibold text-slate-600 text-center w-[60px]">
              Status
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {testResults.map((result) => {
            const hasValue =
              result.result_value !== null && result.result_value !== ""
            return (
              <TableRow
                key={result.id}
                className="hover:bg-slate-50/50 group"
              >
                {/* Test Type - read only */}
                <TableCell className="text-sm font-medium text-slate-900">
                  {result.test_type}
                </TableCell>

                {/* Result - editable */}
                <TableCell className="p-1">
                  {renderCell(result, "result_value", "Enter result")}
                </TableCell>

                {/* Unit - editable */}
                <TableCell className="p-1">
                  {renderCell(result, "unit", "-")}
                </TableCell>

                {/* Spec - read only (comes from ProductTestSpecification) */}
                <TableCell className="text-sm text-slate-600">
                  {result.specification || "-"}
                </TableCell>

                {/* Method - editable */}
                <TableCell className="p-1">
                  {renderCell(result, "method", "-")}
                </TableCell>

                {/* Status indicator */}
                <TableCell className="text-center">
                  {hasValue ? (
                    <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-emerald-100">
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-slate-100">
                      <Circle className="h-3.5 w-3.5 text-slate-400" />
                    </span>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
