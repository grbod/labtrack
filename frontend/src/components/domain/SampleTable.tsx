import React, { useMemo, useState, useCallback } from "react"
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
} from "@tanstack/react-table"
import { ArrowUpDown, ArrowUp, ArrowDown, FileText, Search, ChevronLeft, ChevronRight, ChevronDown, RefreshCw } from "lucide-react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
// Simple select option type for native select elements
type SelectOption = { value: string; label: string }
import { cn } from "@/lib/utils"
import { generateDisplayName } from "@/lib/product-utils"
import { getRelativeTime } from "@/lib/date-utils"
import { STATUS_CONFIG, STATUS_OPTIONS, getStatusColor } from "@/lib/status-config"
import type { Lot, LotType } from "@/types"
import { RetestSubRows } from "./RetestSubRows"

// Lot type display names
const LOT_TYPE_LABELS: Record<LotType, string> = {
  standard: "Standard",
  parent_lot: "Parent Lot",
  sublot: "Sublot",
  multi_sku_composite: "Multi-SKU",
}

// Page size options
const PAGE_SIZE_OPTIONS: SelectOption[] = [
  { value: "10", label: "10 per page" },
  { value: "25", label: "25 per page" },
  { value: "50", label: "50 per page" },
  { value: "100", label: "100 per page" },
]

interface SampleTableProps {
  lots: Lot[]
  onRowClick: (lot: Lot) => void
  onRetestSubRowClick?: (lot: Lot) => void  // Triggers when retest sub-row clicked
  staleWarningDays?: number
  staleCriticalDays?: number
  pageSize?: number
}

/**
 * Calculate age in days from a date string
 */
function getAgeDays(dateString: string): number {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  return Math.floor(diffMs / (1000 * 60 * 60 * 24))
}

const columnHelper = createColumnHelper<Lot>()

export function SampleTable({
  lots,
  onRowClick,
  onRetestSubRowClick,
  staleWarningDays = 7,
  staleCriticalDays = 12,
  pageSize: initialPageSize = 25,
}: SampleTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState("")
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [statusFilter, setStatusFilter] = useState("all")
  const [expandedLotIds, setExpandedLotIds] = useState<Set<number>>(new Set())

  const toggleExpand = useCallback((lotId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    setExpandedLotIds((prev) => {
      const next = new Set(prev)
      if (next.has(lotId)) {
        next.delete(lotId)
      } else {
        next.add(lotId)
      }
      return next
    })
  }, [])

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: "expand",
        header: () => null,
        cell: ({ row }) => {
          const lot = row.original
          // Show chevron for pending/review_required retests
          // Note: Historical retests (completed) are accessible via Sample Modal's Retests History accordion
          const hasActiveRetests = lot.has_pending_retest
          const isExpanded = expandedLotIds.has(lot.id)

          if (!hasActiveRetests) {
            return <div className="w-6" />
          }

          return (
            <button
              type="button"
              onClick={(e) => toggleExpand(lot.id, e)}
              className="p-1 rounded hover:bg-slate-100 transition-colors"
              aria-label={isExpanded ? "Collapse retests" : "Expand retests"}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-amber-600" />
              ) : (
                <ChevronRight className="h-4 w-4 text-amber-600" />
              )}
            </button>
          )
        },
        size: 40,
      }),
      columnHelper.accessor("reference_number", {
        header: ({ column }) => (
          <SortableHeader column={column} label="Reference #" />
        ),
        cell: (info) => (
          <span className="font-mono font-semibold text-slate-900">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("lot_number", {
        header: ({ column }) => (
          <SortableHeader column={column} label="Lot #" />
        ),
        cell: (info) => (
          <span className="font-mono text-slate-700">{info.getValue()}</span>
        ),
      }),
      columnHelper.display({
        id: "product",
        header: ({ column }) => (
          <SortableHeader column={column} label="Product" />
        ),
        cell: ({ row }) => {
          const lot = row.original
          const products = lot.products

          if (!products || products.length === 0) {
            return <span className="text-slate-400">-</span>
          }

          // Multi-product indicator
          if (products.length > 1) {
            const firstProduct = products[0]
            const displayName = generateDisplayName(
              firstProduct.brand,
              firstProduct.product_name,
              firstProduct.flavor ?? undefined,
              firstProduct.size ?? undefined
            )
            return (
              <div>
                <span className="text-slate-700">{displayName}</span>
                <span className="ml-2 inline-flex items-center rounded-md bg-purple-50 px-1.5 py-0.5 text-[10px] font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10">
                  +{products.length - 1} more
                </span>
              </div>
            )
          }

          // Single product - show display name
          const product = products[0]
          const displayName = generateDisplayName(
            product.brand,
            product.product_name,
            product.flavor ?? undefined,
            product.size ?? undefined
          )
          return <span className="text-slate-700">{displayName}</span>
        },
      }),
      columnHelper.accessor("lot_type", {
        id: "type",
        header: ({ column }) => (
          <SortableHeader column={column} label="Type" />
        ),
        cell: (info) => (
          <span className="text-slate-600 capitalize">
            {LOT_TYPE_LABELS[info.getValue()]}
          </span>
        ),
      }),
      columnHelper.accessor("status", {
        header: ({ column }) => (
          <SortableHeader column={column} label="Status" />
        ),
        cell: (info) => {
          const status = info.getValue()
          const config = STATUS_CONFIG[status]
          const lot = info.row.original
          return (
            <div className="flex items-center gap-2">
              <Badge variant={getStatusColor(status)}>
                {config.label}
              </Badge>
              {lot.has_pending_retest && (
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                  <RefreshCw className="h-3 w-3" />
                </span>
              )}
            </div>
          )
        },
        filterFn: (row, columnId, filterValue) => {
          if (filterValue === "all") return true
          return row.getValue(columnId) === filterValue
        },
      }),
      columnHelper.display({
        id: "lab_pdfs",
        header: "Lab PDFs",
        cell: () => (
          <div className="flex items-center gap-1.5 text-slate-400">
            <FileText className="h-4 w-4" />
            <span className="text-sm">-</span>
          </div>
        ),
      }),
      columnHelper.accessor("created_at", {
        header: ({ column }) => (
          <SortableHeader column={column} label="Age" />
        ),
        cell: (info) => {
          const dateString = info.getValue()
          const ageDays = getAgeDays(dateString)
          const relativeTime = getRelativeTime(dateString)

          const isWarning = ageDays >= staleWarningDays && ageDays < staleCriticalDays
          const isCritical = ageDays >= staleCriticalDays

          return (
            <span
              className={cn(
                "text-sm",
                isCritical && "font-semibold text-red-600",
                isWarning && !isCritical && "font-semibold text-orange-600",
                !isWarning && !isCritical && "text-slate-500"
              )}
            >
              {relativeTime}
            </span>
          )
        },
        sortingFn: (rowA, rowB) => {
          const dateA = new Date(rowA.getValue("created_at")).getTime()
          const dateB = new Date(rowB.getValue("created_at")).getTime()
          return dateA - dateB
        },
      }),
    ],
    [staleWarningDays, staleCriticalDays, expandedLotIds, toggleExpand]
  )

  // Apply status filter
  const filteredData = useMemo(() => {
    if (statusFilter === "all") return lots
    return lots.filter((lot) => lot.status === statusFilter)
  }, [lots, statusFilter])

  const table = useReactTable({
    data: filteredData,
    columns,
    state: {
      sorting,
      globalFilter,
      columnFilters,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    globalFilterFn: (row, _columnId, filterValue) => {
      const searchValue = filterValue.toLowerCase()
      const referenceNumber = row.original.reference_number?.toLowerCase() ?? ""
      const lotNumber = row.original.lot_number?.toLowerCase() ?? ""

      // Also search product fields
      const products = row.original.products ?? []
      const productMatch = products.some(p =>
        p.brand.toLowerCase().includes(searchValue) ||
        p.product_name.toLowerCase().includes(searchValue) ||
        (p.flavor?.toLowerCase().includes(searchValue) ?? false)
      )

      return referenceNumber.includes(searchValue) || lotNumber.includes(searchValue) || productMatch
    },
    initialState: {
      pagination: {
        pageSize: initialPageSize,
      },
    },
  })

  /**
   * Get row background class based on age
   */
  const getRowClassName = (lot: Lot): string => {
    const ageDays = getAgeDays(lot.created_at)

    if (ageDays >= staleCriticalDays) {
      return "bg-red-50/50 hover:bg-red-50"
    }
    if (ageDays >= staleWarningDays) {
      return "bg-orange-50/50 hover:bg-orange-50"
    }
    return "hover:bg-slate-50/50"
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search by Reference #, Lot #..."
            value={globalFilter ?? ""}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="pl-10 h-11 bg-white border-slate-200 rounded-lg shadow-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 transition-shadow"
          />
        </div>
        <div className="w-48">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-11 w-full bg-white border border-slate-200 rounded-lg px-3 text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow
                key={headerGroup.id}
                className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100"
              >
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="font-semibold text-slate-600 text-[13px] tracking-wide"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-slate-500"
                >
                  No samples found
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <React.Fragment key={row.id}>
                  <TableRow
                    onClick={() => onRowClick(row.original)}
                    className={cn(
                      "cursor-pointer transition-colors",
                      getRowClassName(row.original)
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id} className="text-[14px]">
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                  {expandedLotIds.has(row.original.id) && (
                    <RetestSubRows
                      lotId={row.original.id}
                      colSpan={columns.length}
                      onRetestClick={() => {
                        if (onRetestSubRowClick) {
                          onRetestSubRowClick(row.original)
                        } else {
                          onRowClick(row.original)
                        }
                      }}
                    />
                  )}
                </React.Fragment>
              ))
            )}
          </TableBody>
        </Table>

        {/* Pagination */}
        <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">
          <div className="flex items-center gap-4">
            <p className="text-[14px] text-slate-500">
              {table.getFilteredRowModel().rows.length} sample
              {table.getFilteredRowModel().rows.length !== 1 ? "s" : ""}
            </p>
            <div className="w-40">
              <select
                value={String(table.getState().pagination.pageSize)}
                onChange={(e) => table.setPageSize(Number(e.target.value))}
                className="h-9 w-full bg-white border border-slate-200 rounded-lg px-3 text-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300"
              >
                {PAGE_SIZE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <p className="text-[14px] text-slate-500">
              Page {table.getState().pagination.pageIndex + 1} of{" "}
              {table.getPageCount() || 1}
            </p>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
                className="border-slate-200 hover:bg-slate-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
                className="border-slate-200 hover:bg-slate-50"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Sortable column header component
 */
interface SortableHeaderProps {
  column: {
    getIsSorted: () => false | "asc" | "desc"
    toggleSorting: (desc?: boolean) => void
  }
  label: string
}

function SortableHeader({ column, label }: SortableHeaderProps) {
  const sorted = column.getIsSorted()

  return (
    <button
      type="button"
      onClick={() => column.toggleSorting(sorted === "asc")}
      className="flex items-center gap-1.5 hover:text-slate-900 transition-colors -ml-2 px-2 py-1 rounded"
    >
      {label}
      {sorted === false && (
        <ArrowUpDown className="h-3.5 w-3.5 text-slate-400" />
      )}
      {sorted === "asc" && <ArrowUp className="h-3.5 w-3.5 text-slate-600" />}
      {sorted === "desc" && <ArrowDown className="h-3.5 w-3.5 text-slate-600" />}
    </button>
  )
}
