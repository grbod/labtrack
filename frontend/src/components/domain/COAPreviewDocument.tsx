import { useState, useRef, useEffect } from "react"
import { parse, format } from "date-fns"
import { Calendar, Pencil } from "lucide-react"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Input } from "@/components/ui/input"
import type { COAPreviewData } from "@/types/release"

interface COAPreviewDocumentProps {
  data: COAPreviewData
  onNotesChange?: (notes: string) => void
  onMfgDateChange?: (date: Date | null) => void
  onExpDateChange?: (date: Date | null) => void
  scale?: number
}

export function COAPreviewDocument({
  data,
  onNotesChange,
  onMfgDateChange,
  onExpDateChange,
  scale = 1,
}: COAPreviewDocumentProps) {
  const [notes, setNotes] = useState(data.notes || "")
  const [isEditingNotes, setIsEditingNotes] = useState(false)
  const [mfgDateOpen, setMfgDateOpen] = useState(false)
  const [expDateOpen, setExpDateOpen] = useState(false)
  const notesRef = useRef<HTMLTextAreaElement>(null)

  // Parse dates from formatted strings (e.g., "January 05, 2026")
  const parseDateString = (dateStr: string | null): Date | undefined => {
    if (!dateStr) return undefined
    try {
      return parse(dateStr, "MMMM dd, yyyy", new Date())
    } catch {
      return undefined
    }
  }

  // Format date for input[type="date"]
  const formatDateForInput = (dateStr: string | null): string => {
    if (!dateStr) return ""
    const date = parseDateString(dateStr)
    if (!date) return ""
    return format(date, "yyyy-MM-dd")
  }

  // Update notes when data changes
  useEffect(() => {
    setNotes(data.notes || "")
  }, [data.notes])

  const handleNotesBlur = () => {
    setIsEditingNotes(false)
    if (notes !== data.notes && onNotesChange) {
      onNotesChange(notes)
    }
  }

  const handleMfgDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setMfgDateOpen(false)
    if (onMfgDateChange) {
      onMfgDateChange(value ? new Date(value) : null)
    }
  }

  const handleExpDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setExpDateOpen(false)
    if (onExpDateChange) {
      onExpDateChange(value ? new Date(value) : null)
    }
  }

  return (
    <div
      className="bg-white shadow-lg origin-top-left transition-transform duration-200"
      style={{
        width: `${8.5 * 96}px`, // 8.5 inches at 96 DPI (816px)
        minHeight: `${11 * 96}px`, // 11 inches at 96 DPI (1056px)
        padding: `${0.5 * 96}px`, // 0.5 inch margins (48px)
        fontFamily: "'Helvetica Neue', Arial, sans-serif",
        fontSize: "10pt",
        lineHeight: 1.4,
        color: "#1e293b",
        transform: `scale(${scale})`,
        transformOrigin: "top left",
      }}
    >
      {/* Header */}
      <div
        className="flex justify-between items-start pb-4 mb-6"
        style={{ borderBottom: "2px solid #1e293b" }}
      >
        <div>
          <h1
            className="font-bold text-slate-900"
            style={{ fontSize: "18pt", marginBottom: "4px" }}
          >
            {data.company_name || "Company Name"}
          </h1>
          {data.company_address && (
            <p className="text-slate-500" style={{ fontSize: "9pt" }}>
              {data.company_address}
            </p>
          )}
          {(data.company_phone || data.company_email) && (
            <p className="text-slate-500" style={{ fontSize: "9pt" }}>
              {data.company_phone && `Tel: ${data.company_phone}`}
              {data.company_phone && data.company_email && " | "}
              {data.company_email && `Email: ${data.company_email}`}
            </p>
          )}
        </div>
        <div className="text-right">
          <h2
            className="font-bold text-slate-900 uppercase tracking-wider"
            style={{ fontSize: "14pt" }}
          >
            Certificate of Analysis
          </h2>
          <p className="text-slate-500 mt-1" style={{ fontSize: "9pt" }}>
            Document #: COA-{data.reference_number}
          </p>
          <p className="text-slate-500" style={{ fontSize: "9pt" }}>
            Generated: {data.generated_date}
          </p>
        </div>
      </div>

      {/* Product Information Section */}
      <div
        className="mb-6 rounded-md"
        style={{
          backgroundColor: "#f8fafc",
          border: "1px solid #e2e8f0",
          padding: "16px",
        }}
      >
        <h3
          className="font-semibold text-slate-900 uppercase tracking-wide mb-3"
          style={{ fontSize: "11pt", letterSpacing: "0.5px" }}
        >
          Product Information
        </h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span
              className="font-semibold text-slate-500 uppercase block"
              style={{ fontSize: "8pt", letterSpacing: "0.5px" }}
            >
              Product Name
            </span>
            <span className="font-medium text-slate-900" style={{ fontSize: "10pt" }}>
              {data.product_name || "N/A"}
            </span>
          </div>
          <div>
            <span
              className="font-semibold text-slate-500 uppercase block"
              style={{ fontSize: "8pt", letterSpacing: "0.5px" }}
            >
              Brand
            </span>
            <span className="font-medium text-slate-900" style={{ fontSize: "10pt" }}>
              {data.brand || "N/A"}
            </span>
          </div>
          <div>
            <span
              className="font-semibold text-slate-500 uppercase block"
              style={{ fontSize: "8pt", letterSpacing: "0.5px" }}
            >
              Lot Number
            </span>
            <span className="font-medium text-slate-900" style={{ fontSize: "10pt" }}>
              {data.lot_number || "N/A"}
            </span>
          </div>
          <div>
            <span
              className="font-semibold text-slate-500 uppercase block"
              style={{ fontSize: "8pt", letterSpacing: "0.5px" }}
            >
              Reference Number
            </span>
            <span className="font-medium text-slate-900" style={{ fontSize: "10pt" }}>
              {data.reference_number || "N/A"}
            </span>
          </div>

          {/* Editable Manufacturing Date */}
          <div>
            <span
              className="font-semibold text-slate-500 uppercase block"
              style={{ fontSize: "8pt", letterSpacing: "0.5px" }}
            >
              Manufacturing Date
            </span>
            <Popover open={mfgDateOpen} onOpenChange={setMfgDateOpen}>
              <PopoverTrigger asChild>
                <button
                  className="group flex items-center gap-1 font-medium text-slate-900 hover:text-blue-600 transition-colors"
                  style={{ fontSize: "10pt" }}
                >
                  <span
                    className="border-b border-dashed border-slate-300 group-hover:border-blue-400"
                  >
                    {data.mfg_date || "Not set"}
                  </span>
                  <Calendar
                    className="h-3 w-3 text-slate-400 group-hover:text-blue-500"
                    style={{ width: "12px", height: "12px" }}
                  />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-3" align="start">
                <Input
                  type="date"
                  defaultValue={formatDateForInput(data.mfg_date)}
                  onChange={handleMfgDateChange}
                  className="w-[180px]"
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Editable Expiration Date */}
          <div>
            <span
              className="font-semibold text-slate-500 uppercase block"
              style={{ fontSize: "8pt", letterSpacing: "0.5px" }}
            >
              Expiration Date
            </span>
            <Popover open={expDateOpen} onOpenChange={setExpDateOpen}>
              <PopoverTrigger asChild>
                <button
                  className="group flex items-center gap-1 font-medium text-slate-900 hover:text-blue-600 transition-colors"
                  style={{ fontSize: "10pt" }}
                >
                  <span
                    className="border-b border-dashed border-slate-300 group-hover:border-blue-400"
                  >
                    {data.exp_date || "Not set"}
                  </span>
                  <Calendar
                    className="h-3 w-3 text-slate-400 group-hover:text-blue-500"
                    style={{ width: "12px", height: "12px" }}
                  />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-3" align="start">
                <Input
                  type="date"
                  defaultValue={formatDateForInput(data.exp_date)}
                  onChange={handleExpDateChange}
                  className="w-[180px]"
                />
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>

      {/* Test Results Section */}
      <div className="mb-6">
        <h3
          className="font-semibold text-slate-900 uppercase tracking-wide mb-3"
          style={{ fontSize: "11pt", letterSpacing: "0.5px" }}
        >
          Test Results
        </h3>
        <table
          className="w-full"
          style={{
            borderCollapse: "collapse",
            border: "1px solid #e2e8f0",
            borderRadius: "6px",
          }}
        >
          <thead>
            <tr style={{ backgroundColor: "#f1f5f9" }}>
              <th
                className="text-left font-semibold text-slate-600 uppercase"
                style={{
                  padding: "10px 12px",
                  fontSize: "8pt",
                  letterSpacing: "0.5px",
                  borderBottom: "1px solid #e2e8f0",
                  width: "30%",
                }}
              >
                Test Name
              </th>
              <th
                className="text-left font-semibold text-slate-600 uppercase"
                style={{
                  padding: "10px 12px",
                  fontSize: "8pt",
                  letterSpacing: "0.5px",
                  borderBottom: "1px solid #e2e8f0",
                  width: "20%",
                }}
              >
                Result
              </th>
              <th
                className="text-left font-semibold text-slate-600 uppercase"
                style={{
                  padding: "10px 12px",
                  fontSize: "8pt",
                  letterSpacing: "0.5px",
                  borderBottom: "1px solid #e2e8f0",
                  width: "20%",
                }}
              >
                Specification
              </th>
              <th
                className="text-left font-semibold text-slate-600 uppercase"
                style={{
                  padding: "10px 12px",
                  fontSize: "8pt",
                  letterSpacing: "0.5px",
                  borderBottom: "1px solid #e2e8f0",
                  width: "10%",
                }}
              >
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {data.tests.length > 0 ? (
              data.tests.map((test, idx) => (
                <tr
                  key={idx}
                  style={{
                    backgroundColor: idx % 2 === 1 ? "#f8fafc" : "white",
                  }}
                >
                  <td
                    className="text-slate-900"
                    style={{
                      padding: "10px 12px",
                      fontSize: "9pt",
                      borderBottom: idx === data.tests.length - 1 ? "none" : "1px solid #e2e8f0",
                    }}
                  >
                    {test.name}
                  </td>
                  <td
                    className="text-slate-900"
                    style={{
                      padding: "10px 12px",
                      fontSize: "9pt",
                      borderBottom: idx === data.tests.length - 1 ? "none" : "1px solid #e2e8f0",
                    }}
                  >
                    {test.result} {test.unit && test.unit}
                  </td>
                  <td
                    className="text-slate-900"
                    style={{
                      padding: "10px 12px",
                      fontSize: "9pt",
                      borderBottom: idx === data.tests.length - 1 ? "none" : "1px solid #e2e8f0",
                    }}
                  >
                    {test.specification}
                  </td>
                  <td
                    className={test.status === "Pass" ? "text-emerald-600 font-semibold" : "text-red-600 font-semibold"}
                    style={{
                      padding: "10px 12px",
                      fontSize: "9pt",
                      borderBottom: idx === data.tests.length - 1 ? "none" : "1px solid #e2e8f0",
                    }}
                  >
                    {test.status === "Pass" ? "Pass" : "Fail"}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={4}
                  className="text-center text-slate-500 italic"
                  style={{
                    padding: "20px",
                    fontSize: "9pt",
                  }}
                >
                  No test results available
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Notes Section (Editable) */}
      <div className="mb-6">
        <h3
          className="font-semibold text-slate-900 uppercase tracking-wide mb-2"
          style={{ fontSize: "11pt", letterSpacing: "0.5px" }}
        >
          Notes
        </h3>
        <div
          className="relative group"
          style={{
            backgroundColor: "#fefce8",
            border: "1px solid #fef08a",
            borderRadius: "6px",
            padding: "12px",
          }}
        >
          {isEditingNotes ? (
            <textarea
              ref={notesRef}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onBlur={handleNotesBlur}
              className="w-full bg-transparent resize-none outline-none text-amber-900"
              style={{
                fontSize: "9pt",
                minHeight: "60px",
              }}
              placeholder="Add notes about this COA..."
              autoFocus
            />
          ) : (
            <div
              onClick={() => {
                setIsEditingNotes(true)
                setTimeout(() => notesRef.current?.focus(), 0)
              }}
              className="cursor-text min-h-[40px] text-amber-900 whitespace-pre-wrap"
              style={{ fontSize: "9pt" }}
            >
              {notes || (
                <span className="text-amber-600/60 italic">Click to add notes...</span>
              )}
              <Pencil
                className="absolute top-2 right-2 h-4 w-4 text-amber-400 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ width: "14px", height: "14px" }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Authorization Section */}
      <div
        className="mb-6 pt-4"
        style={{ borderTop: "1px solid #e2e8f0" }}
      >
        <h3
          className="font-semibold text-slate-900 uppercase tracking-wide mb-3"
          style={{ fontSize: "11pt", letterSpacing: "0.5px" }}
        >
          Authorization
        </h3>
        <div className="flex justify-between">
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-slate-600" style={{ fontSize: "9pt" }}>
                Released By:
              </span>
              <span
                className="border-b border-slate-400 inline-block"
                style={{ width: "150px" }}
              >
                {data.released_by && (
                  <span className="text-slate-900" style={{ fontSize: "9pt" }}>
                    {data.released_by}
                  </span>
                )}
              </span>
              <span className="text-slate-600" style={{ fontSize: "9pt" }}>
                Date:
              </span>
              <span
                className="border-b border-slate-400 inline-block"
                style={{ width: "100px" }}
              >
                {data.released_by && (
                  <span className="text-slate-900" style={{ fontSize: "9pt" }}>
                    {data.generated_date}
                  </span>
                )}
              </span>
            </div>
            <div className="flex items-baseline gap-2 mt-3">
              <span className="text-slate-600" style={{ fontSize: "9pt" }}>
                Quality Assurance:
              </span>
              <span
                className="border-b border-slate-400 inline-block"
                style={{ width: "120px" }}
              />
              <span className="text-slate-600" style={{ fontSize: "9pt" }}>
                Date:
              </span>
              <span
                className="border-b border-slate-400 inline-block"
                style={{ width: "100px" }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Disclaimer Footer */}
      <div
        className="text-center text-slate-500"
        style={{
          backgroundColor: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "6px",
          padding: "12px",
          fontSize: "7pt",
        }}
      >
        This Certificate of Analysis is issued based on the test results of a representative sample.
        Results apply only to the lot specified above. This document is electronically generated and valid without signature.
      </div>
    </div>
  )
}
