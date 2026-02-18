import { z } from "zod"

/**
 * Lab Test Type row schema
 * Mirrors backend LabTestTypeBulkImportRow
 */
export const labTestTypeGridSchema = z.object({
  id: z.string(),
  test_name: z
    .string()
    .min(1, "Test name is required")
    .max(100, "Max 100 characters")
    .refine((val) => val.trim().length > 0, "Cannot be only whitespace"),
  test_category: z
    .string()
    .min(1, "Category is required")
    .max(50, "Max 50 characters"),
  default_unit: z
    .string()
    .max(20, "Max 20 characters")
    .optional()
    .or(z.literal("")),
  test_method: z
    .string()
    .max(100, "Max 100 characters")
    .optional()
    .or(z.literal("")),
  default_specification: z
    .string()
    .max(100, "Max 100 characters")
    .optional()
    .or(z.literal("")),
  abbreviations: z
    .string()
    .max(200, "Max 200 characters")
    .optional()
    .or(z.literal("")),
  description: z
    .string()
    .max(500, "Max 500 characters")
    .optional()
    .or(z.literal("")),
  _errors: z.array(z.string()).optional(),
  _rowError: z.string().optional(),
})

export type LabTestTypeGridRow = z.infer<typeof labTestTypeGridSchema>

/**
 * Product row schema
 * Mirrors backend ProductBulkImportRow
 * Note: display_name is auto-generated from brand + product_name + flavor + size + version
 */
export const productGridSchema = z.object({
  id: z.string(),
  brand: z
    .string()
    .min(1, "Brand is required")
    .max(100, "Max 100 characters"),
  product_name: z
    .string()
    .min(1, "Product name is required")
    .max(200, "Max 200 characters"),
  flavor: z.string().max(100, "Max 100 characters").optional().or(z.literal("")),
  size: z.string().max(50, "Max 50 characters").optional().or(z.literal("")),
  version: z.string().max(10, "Max 10 characters").optional().or(z.literal("")),
  serving_size: z
    .string()
    .max(50, "Max 50 characters")
    .optional()
    .or(z.literal("")),
  expiry_duration_months: z.coerce
    .number()
    .int("Expiry must be a whole number")
    .positive("Expiry must be positive")
    .max(120, "Expiry max 120 months")
    .default(36),
  _errors: z.array(z.string()).optional(),
  _rowError: z.string().optional(),
  _touched: z.boolean().optional(),
})

export type ProductGridRow = z.infer<typeof productGridSchema>

/**
 * Validate a row and return errors
 * @param schema - Zod schema to validate against
 * @param row - Row data to validate
 * @returns Validation result with error messages
 */
export function validateRow<T>(
  schema: z.ZodSchema<T>,
  row: any
): { valid: boolean; errors: string[] } {
  try {
    const result = schema.safeParse(row)

    if (result.success) {
      return { valid: true, errors: [] }
    }

    // Defensive check for result.error and result.error.issues
    if (!result.error || !result.error.issues) {
      console.error("Unexpected Zod error format:", result)
      return { valid: false, errors: ["Validation failed with unknown error"] }
    }

    return {
      valid: false,
      errors: result.error.issues.map((e) => {
        const field = e.path.join(".")
        const message = e.message
        return field ? `${field}: ${message}` : message
      }),
    }
  } catch (error) {
    console.error("Error during validation:", error)
    return { valid: false, errors: [`Validation error: ${error}`] }
  }
}

/**
 * Validate all rows and update their _errors field
 * @param rows - Array of rows to validate
 * @param schema - Zod schema
 * @returns Updated rows with _errors populated
 */
export function validateAllRows<T extends { id: string; _errors?: string[] }>(
  rows: T[],
  schema: z.ZodSchema<T>
): T[] {
  return rows.map((row) => {
    const { valid, errors } = validateRow(schema, row)
    return {
      ...row,
      _errors: valid ? undefined : errors,
    }
  })
}

/**
 * Get only valid rows (no errors)
 */
export function getValidRows<
  T extends { _errors?: string[]; _rowError?: string }
>(rows: T[]): T[] {
  return rows.filter((row) => !row._errors?.length && !row._rowError)
}

/**
 * Get rows with errors
 */
export function getInvalidRows<
  T extends { _errors?: string[]; _rowError?: string }
>(rows: T[]): T[] {
  return rows.filter((row) => row._errors?.length || row._rowError)
}
