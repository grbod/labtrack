import { useState, useMemo } from "react"
import { motion } from "framer-motion"
import {
  Search,
  Loader2,
  Archive as ArchiveIcon,
  Download,
  Mail,
  Filter,
  X,
  ChevronUp,
  ChevronDown,
} from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { useArchive, useCustomers, useSendEmail, useDownloadWithTracking } from "@/hooks/useRelease"
import { useProducts } from "@/hooks/useProducts"
import { Badge } from "@/components/ui/badge"
import { formatDate } from "@/lib/date-utils"
import type { ArchiveFilters, ArchiveItem } from "@/types/release"

export function ArchivePage() {
  const [search, setSearch] = useState("")
  const [productId, setProductId] = useState<number | undefined>()
  const [customerId, setCustomerId] = useState<number | undefined>()
  const [dateFrom, setDateFrom] = useState("")
  const [dateTo, setDateTo] = useState("")
  const [lotNumber, setLotNumber] = useState("")
  const [showFilters, setShowFilters] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [sortBy, setSortBy] = useState<ArchiveFilters['sort_by']>('released_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // Email dialog state
  const [emailDialogOpen, setEmailDialogOpen] = useState(false)
  const [emailTarget, setEmailTarget] = useState<{ lotId: number; productId: number } | null>(null)
  const [emailRecipient, setEmailRecipient] = useState("")


  // Build filters object
  const filters: ArchiveFilters = useMemo(
    () => ({
      search: search || undefined,
      product_id: productId,
      customer_id: customerId,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      lot_number: lotNumber || undefined,
      page,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
    }),
    [search, productId, customerId, dateFrom, dateTo, lotNumber, page, pageSize, sortBy, sortOrder]
  )

  const { data: archiveData, isLoading } = useArchive(filters)
  const { data: productsData } = useProducts({ page_size: 500 })
  const { data: customers = [] } = useCustomers()
  const sendEmail = useSendEmail()
  const { handleDownload, isDownloading } = useDownloadWithTracking()

  const hasActiveFilters = productId || customerId || dateFrom || dateTo || lotNumber

  const handleClearFilters = () => {
    setProductId(undefined)
    setCustomerId(undefined)
    setDateFrom("")
    setDateTo("")
    setLotNumber("")
    setPage(1)
  }

  const handleSort = (column: ArchiveFilters['sort_by']) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(column)
      setSortOrder('desc')
    }
    setPage(1)
  }

  const SortableHeader = ({
    column,
    label
  }: {
    column: ArchiveFilters['sort_by']
    label: string
  }) => (
    <TableHead
      className="text-[12px] font-semibold text-slate-600 cursor-pointer hover:bg-slate-100 select-none"
      onClick={() => handleSort(column)}
    >
      <div className="flex items-center gap-1">
        {label}
        {sortBy === column && (
          sortOrder === 'asc'
            ? <ChevronUp className="h-3.5 w-3.5" />
            : <ChevronDown className="h-3.5 w-3.5" />
        )}
      </div>
    </TableHead>
  )

  const handleResendEmail = (item: ArchiveItem) => {
    setEmailTarget({ lotId: item.lot_id, productId: item.product_id })
    setEmailRecipient("")
    setEmailDialogOpen(true)
  }

  const handleSendEmail = async () => {
    if (!emailTarget || !emailRecipient.trim()) return

    try {
      await sendEmail.mutateAsync({
        lotId: emailTarget.lotId,
        productId: emailTarget.productId,
        recipientEmail: emailRecipient.trim(),
      })
      setEmailDialogOpen(false)
      setEmailTarget(null)
      setEmailRecipient("")
    } catch (error) {
      console.error("Failed to send email:", error)
    }
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.275 }}
        className="space-y-6"
      >
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">
          History
        </h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Search and download released COAs
        </p>
      </div>

      {/* Search and Filters */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-4">
          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              type="text"
              placeholder="Search by reference number, product, or lot..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Filter Toggle */}
          <Button
            variant={showFilters || hasActiveFilters ? "default" : "outline"}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="h-4 w-4" />
            Filters
            {hasActiveFilters && (
              <span className="ml-1 rounded-full bg-white/20 px-1.5 py-0.5 text-[10px]">
                {[productId, customerId, dateFrom, dateTo, lotNumber].filter(Boolean).length}
              </span>
            )}
          </Button>

          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={handleClearFilters}>
              <X className="h-4 w-4" />
              Clear
            </Button>
          )}
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <Label className="text-[12px] text-slate-600 mb-1.5 block">
                Product
              </Label>
              <select
                value={productId ?? ""}
                onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-[13px]"
              >
                <option value="">All products</option>
                {productsData?.items.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.display_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label className="text-[12px] text-slate-600 mb-1.5 block">
                Customer
              </Label>
              <select
                value={customerId ?? ""}
                onChange={(e) => setCustomerId(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-[13px]"
              >
                <option value="">All customers</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.company_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label className="text-[12px] text-slate-600 mb-1.5 block">
                Date From
              </Label>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="text-[13px]"
              />
            </div>

            <div>
              <Label className="text-[12px] text-slate-600 mb-1.5 block">
                Date To
              </Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="text-[13px]"
              />
            </div>

            <div>
              <Label className="text-[12px] text-slate-600 mb-1.5 block">
                Lot Number
              </Label>
              <Input
                type="text"
                placeholder="Enter lot number"
                value={lotNumber}
                onChange={(e) => setLotNumber(e.target.value)}
                className="text-[13px]"
              />
            </div>
          </div>
        )}
      </div>

      {/* Results Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : !archiveData?.items.length ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="rounded-xl bg-slate-100 p-4">
              <ArchiveIcon className="h-8 w-8 text-slate-400" />
            </div>
            <p className="mt-4 text-[14px] font-medium text-slate-600">
              No COAs found
            </p>
            <p className="mt-1 text-[13px] text-slate-500">
              {hasActiveFilters || search
                ? "Try adjusting your search or filters"
                : "Released COAs will appear here"}
            </p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80">
                  <SortableHeader column="reference_number" label="Ref" />
                  <SortableHeader column="lot_number" label="Lot" />
                  <SortableHeader column="brand" label="Brand" />
                  <SortableHeader column="product_name" label="Product" />
                  <SortableHeader column="released_at" label="Released Date" />
                  <TableHead className="text-[12px] font-semibold text-slate-600">Customer</TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">Status</TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600 text-right">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {archiveData.items.map((item) => (
                  <TableRow key={`${item.lot_id}-${item.product_id}`} className="hover:bg-slate-50/80">
                    <TableCell className="font-mono text-[13px] font-medium text-slate-900">
                      {item.reference_number}
                    </TableCell>
                    <TableCell className="font-mono text-[13px] text-slate-600">
                      {item.lot_number || '—'}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {item.brand}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-700">
                      {item.product_name}
                      {item.flavor && <span className="text-slate-500"> - {item.flavor}</span>}
                      {item.size && <span className="text-slate-400 ml-1">({item.size})</span>}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {formatDate(item.released_at)}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {item.customer_name || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="emerald" className="text-[11px]">Released</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title="Download COA"
                          onClick={() => handleDownload(item.lot_id, item.product_id)}
                          disabled={isDownloading(item.lot_id, item.product_id)}
                          className={`h-8 w-8 rounded-md border border-slate-200 bg-white shadow-sm hover:bg-slate-50 hover:shadow active:shadow-none active:bg-slate-100 transition-all ${isDownloading(item.lot_id, item.product_id) ? "cursor-wait" : ""}`}
                        >
                          {isDownloading(item.lot_id, item.product_id) ? (
                            <Loader2 className="h-4 w-4 text-slate-600 animate-spin" />
                          ) : (
                            <Download className="h-4 w-4 text-slate-600" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleResendEmail(item)}
                          title="Re-send email"
                          className="h-8 w-8 rounded-md border border-slate-200 bg-white shadow-sm hover:bg-slate-50 hover:shadow active:shadow-none active:bg-slate-100 transition-all"
                        >
                          <Mail className="h-4 w-4 text-slate-600" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Pagination */}
            <div className="px-4 py-3 border-t border-slate-200 bg-slate-50/50 flex items-center justify-between">
              <p className="text-[12px] text-slate-500">
                Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, archiveData.total)} of {archiveData.total}
              </p>

              <div className="flex items-center gap-4">
                {/* Page size selector */}
                <div className="flex items-center gap-2">
                  <span className="text-[12px] text-slate-500">Rows:</span>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value))
                      setPage(1)
                    }}
                    className="h-8 rounded-md border border-slate-200 bg-white px-2 text-[12px]"
                  >
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>

                {/* Page navigation */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </Button>
                  <span className="text-[12px] text-slate-600 min-w-[80px] text-center">
                    Page {page} of {archiveData.total_pages || 1}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.min(archiveData.total_pages || 1, p + 1))}
                    disabled={page >= (archiveData.total_pages || 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Email Dialog */}
      <Dialog open={emailDialogOpen} onOpenChange={setEmailDialogOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Re-send COA via Email</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Label htmlFor="emailRecipient">Recipient Email</Label>
            <Input
              id="emailRecipient"
              type="email"
              value={emailRecipient}
              onChange={(e) => setEmailRecipient(e.target.value)}
              placeholder="Enter recipient email"
              className="mt-2"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSendEmail}
              disabled={!emailRecipient.trim() || sendEmail.isPending}
            >
              {sendEmail.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Send Email
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </motion.div>
    </div>
  )
}
