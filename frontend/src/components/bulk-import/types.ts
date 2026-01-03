import { z } from "zod"
import type { ColumnDef } from "@tanstack/react-table"

/**
 * Base interface for all grid rows
 * - id: Unique identifier (nanoid)
 * - _errors: Array of validation error messages for this row
 * - _rowError: Single error message for row-level failures
 */
export interface BulkImportRow {
  id: string
  _errors?: string[]
  _rowError?: string
}

/**
 * Backend response from bulk import API
 */
export interface BulkImportResult {
  total_rows: number
  imported: number
  skipped: number
  errors: string[] // Format: "Row X: error message"
}

/**
 * Cell edit state tracking
 */
export interface EditingCell {
  rowId: string
  columnId: string
}

/**
 * Generic grid props for reusable BulkImportGrid component
 */
export interface BulkImportGridProps<T extends BulkImportRow> {
  // Data
  data: T[]
  setData: React.Dispatch<React.SetStateAction<T[]>>

  // Column configuration
  columns: ColumnDef<T>[]
  editableColumns: string[] // IDs of columns that support Tab navigation

  // Validation
  schema: z.ZodSchema<T>
  validateRow: (row: T) => { valid: boolean; errors: string[] }

  // Actions
  onSubmit: (validRows: Omit<T, "id" | "_errors" | "_rowError">[]) => Promise<void>
  onExportTemplate: () => void
  onImportFile: (file: File) => Promise<void>
  onPaste?: (e: React.ClipboardEvent) => void

  // UI Configuration
  title: string
  submitButtonText?: string
  templateFilename: string

  // Loading states
  isSubmitting?: boolean

  // Factory for empty rows
  createEmptyRow: () => T
}
