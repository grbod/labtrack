import * as XLSX from "xlsx"
import { nanoid } from "nanoid"

/**
 * Export template Excel file with column headers
 * @param headers - Column header names
 * @param filename - Output filename (without extension)
 */
export function exportTemplate(headers: string[], filename: string): void {
  // Create worksheet with headers
  const worksheet = XLSX.utils.aoa_to_sheet([headers])

  // Set column widths for better UX
  const colWidths = headers.map((h) => ({
    wch: Math.max(h.length + 5, 15), // Minimum 15, or header length + padding
  }))
  worksheet["!cols"] = colWidths

  // Create workbook and add worksheet
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, "Template")

  // Download file
  XLSX.writeFile(workbook, `${filename}.xlsx`)
}

/**
 * Parse Excel/CSV file into row objects
 * @param file - File object from input
 * @param columnMapping - Map of "Excel Column Name" -> "row property key"
 * @param defaultValues - Default values for optional fields
 * @returns Promise resolving to array of row objects
 */
export async function parseExcelFile<T extends Record<string, any>>(
  file: File,
  columnMapping: Record<string, keyof T>,
  defaultValues?: Partial<T>
): Promise<T[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const data = e.target?.result
        const workbook = XLSX.read(data, { type: "binary" })

        // Get first worksheet
        const worksheetName = workbook.SheetNames[0]
        const worksheet = workbook.Sheets[worksheetName]

        // Convert to JSON (array of objects with header keys)
        const rawRows = XLSX.utils.sheet_to_json<Record<string, any>>(worksheet)

        // Map to typed row objects
        const mappedRows = rawRows.map((rawRow) => {
          const row: any = {
            id: nanoid(),
            ...defaultValues,
          }

          // Map each column according to columnMapping
          Object.entries(columnMapping).forEach(([excelCol, rowKey]) => {
            const value = rawRow[excelCol]

            // Handle different value types
            if (value !== undefined && value !== null) {
              // Convert numbers if needed
              if (typeof row[rowKey] === "number") {
                row[rowKey] =
                  typeof value === "number" ? value : parseFloat(value) || 0
              } else {
                row[rowKey] = String(value).trim()
              }
            }
          })

          return row as T
        })

        resolve(mappedRows)
      } catch (error) {
        reject(new Error(`Failed to parse Excel file: ${error}`))
      }
    }

    reader.onerror = () => {
      reject(new Error("Failed to read file"))
    }

    reader.readAsBinaryString(file)
  })
}

/**
 * Parse clipboard data (tab-separated values from Excel copy)
 * @param clipboardText - Text from clipboard
 * @param columnOrder - Array of column keys in expected order
 * @param defaultValues - Default values for optional fields
 * @returns Array of row objects
 */
export function parseClipboardData<T extends Record<string, any>>(
  clipboardText: string,
  columnOrder: (keyof T)[],
  defaultValues?: Partial<T>
): T[] {
  const lines = clipboardText.split("\n").filter((line) => line.trim())

  return lines.map((line) => {
    const cells = line.split("\t")
    const row: any = {
      id: nanoid(),
      ...defaultValues,
    }

    columnOrder.forEach((key, index) => {
      const value = cells[index]?.trim()
      if (value) {
        // Try to parse as number if field expects number
        if (typeof defaultValues?.[key] === "number") {
          row[key] = parseFloat(value) || defaultValues[key]
        } else {
          row[key] = value
        }
      }
    })

    return row as T
  })
}

/**
 * Export data to Excel file
 * @param data - Array of row objects
 * @param filename - Output filename
 * @param columnHeaders - Map of property keys to display headers
 */
export function exportToExcel<T extends Record<string, any>>(
  data: T[],
  filename: string,
  columnHeaders: Record<keyof T, string>
): void {
  // Convert data to 2D array
  const headers = Object.values(columnHeaders)
  const keys = Object.keys(columnHeaders) as (keyof T)[]

  const rows = data.map((row) => keys.map((key) => row[key] ?? ""))

  const sheetData = [headers, ...rows]

  // Create worksheet
  const worksheet = XLSX.utils.aoa_to_sheet(sheetData)

  // Set column widths
  const colWidths = headers.map((h) => ({
    wch: Math.max(String(h).length + 5, 15),
  }))
  worksheet["!cols"] = colWidths

  // Create workbook
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, "Data")

  // Download
  XLSX.writeFile(workbook, `${filename}.xlsx`)
}
