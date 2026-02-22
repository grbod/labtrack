import { useState, useRef, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Archive, Package, FlaskConical, Users, Search, Loader2, RotateCcw, Beaker, Keyboard } from "lucide-react"
import { format } from "date-fns"

import { toast } from "sonner"
import { extractApiErrorMessage } from "@/lib/api-utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EmptyState } from "@/components/ui/empty-state"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"

import { productsApi } from "@/api/products"
import { labTestTypesApi } from "@/api/labTestTypes"
import { customersApi } from "@/api/customers"
import { useArchivedLots } from "@/hooks/useLots"
import type { Product, LabTestType, Customer, ArchivedLot } from "@/types"

type ArchivedTab = "samples" | "products" | "lab-tests" | "customers"

export function ArchivedItemsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<ArchivedTab>("samples")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState("")

  // Restore confirmation dialog state
  const [restoreDialog, setRestoreDialog] = useState<{
    type: ArchivedTab
    item: Product | LabTestType | Customer
  } | null>(null)

  // Keyboard shortcut state for row navigation (using refs to avoid effect re-runs)
  const pendingDigitRef = useRef<string | null>(null)
  const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Samples (completed lots) query - only fetch when samples tab is active
  const samplesQuery = useArchivedLots(
    activeTab === "samples"
      ? { page, page_size: pageSize, search: search || undefined }
      : { page: 1, page_size: 1 }, // Minimal query when not active
    activeTab === "samples"
  )

  // Products query
  const productsQuery = useQuery({
    queryKey: ["archivedProducts", page, pageSize, search],
    queryFn: () => productsApi.listArchived({ page, page_size: pageSize, search: search || undefined }),
    enabled: activeTab === "products",
  })

  // Lab test types query
  const labTestsQuery = useQuery({
    queryKey: ["archivedLabTests", page, pageSize, search],
    queryFn: () => labTestTypesApi.listArchived({ page, page_size: pageSize, search: search || undefined }),
    enabled: activeTab === "lab-tests",
  })

  // Customers query
  const customersQuery = useQuery({
    queryKey: ["archivedCustomers", page, pageSize, search],
    queryFn: () => customersApi.listArchived({ page, page_size: pageSize, search: search || undefined }),
    enabled: activeTab === "customers",
  })

  // Restore mutations
  const restoreProductMutation = useMutation({
    mutationFn: productsApi.restore,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archivedProducts"] })
      queryClient.invalidateQueries({ queryKey: ["products"] })
      setRestoreDialog(null)
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to restore product"))
    },
  })

  const restoreLabTestMutation = useMutation({
    mutationFn: labTestTypesApi.restore,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archivedLabTests"] })
      queryClient.invalidateQueries({ queryKey: ["labTestTypes"] })
      setRestoreDialog(null)
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to restore lab test type"))
    },
  })

  const restoreCustomerMutation = useMutation({
    mutationFn: customersApi.restore,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archivedCustomers"] })
      queryClient.invalidateQueries({ queryKey: ["customers"] })
      setRestoreDialog(null)
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to restore customer"))
    },
  })

  const handleRestore = () => {
    if (!restoreDialog) return

    switch (restoreDialog.type) {
      case "products":
        restoreProductMutation.mutate(restoreDialog.item.id)
        break
      case "lab-tests":
        restoreLabTestMutation.mutate(restoreDialog.item.id)
        break
      case "customers":
        restoreCustomerMutation.mutate(restoreDialog.item.id)
        break
    }
  }

  const isRestoring = restoreProductMutation.isPending ||
    restoreLabTestMutation.isPending ||
    restoreCustomerMutation.isPending

  // Navigate to a specific row in the samples list
  const navigateToRow = useCallback((rowNum: number) => {
    const items = samplesQuery.data?.items
    if (!items || rowNum < 1 || rowNum > items.length) return
    const sample = items[rowNum - 1]
    navigate(`/audittrail/lot/${sample.lot_id}/${sample.product_id}`)
  }, [samplesQuery.data, navigate])

  // Keyboard shortcuts for row navigation (samples tab only)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only on samples tab
      if (activeTab !== "samples") return

      // Skip if restore dialog is open
      if (restoreDialog) return

      // Skip if typing in input
      const activeEl = document.activeElement as HTMLElement
      if (activeEl?.tagName === "INPUT" || activeEl?.tagName === "TEXTAREA") return

      // Only handle digits 0-9
      if (!/^[0-9]$/.test(e.key)) {
        // Clear pending digit on non-digit key
        if (pendingTimeoutRef.current) {
          clearTimeout(pendingTimeoutRef.current)
          pendingTimeoutRef.current = null
        }
        pendingDigitRef.current = null
        return
      }

      e.preventDefault()

      if (pendingDigitRef.current) {
        // Two-digit sequence complete
        const rowNum = parseInt(pendingDigitRef.current + e.key, 10)
        if (pendingTimeoutRef.current) {
          clearTimeout(pendingTimeoutRef.current)
          pendingTimeoutRef.current = null
        }
        pendingDigitRef.current = null
        navigateToRow(rowNum)
      } else if (e.key !== "0") {
        // Start sequence (can't start with 0)
        pendingDigitRef.current = e.key
        pendingTimeoutRef.current = setTimeout(() => {
          // Single digit after 300ms timeout
          const digit = pendingDigitRef.current
          pendingDigitRef.current = null
          pendingTimeoutRef.current = null
          if (digit) {
            navigateToRow(parseInt(digit, 10))
          }
        }, 300)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      if (pendingTimeoutRef.current) {
        clearTimeout(pendingTimeoutRef.current)
        pendingTimeoutRef.current = null
      }
      pendingDigitRef.current = null
    }
  }, [activeTab, navigateToRow, restoreDialog])

  const tabs = [
    { id: "samples" as const, label: "Completed Samples", icon: <Beaker className="h-4 w-4" /> },
    { id: "products" as const, label: "Products", icon: <Package className="h-4 w-4" /> },
    { id: "lab-tests" as const, label: "Lab Tests", icon: <FlaskConical className="h-4 w-4" /> },
    { id: "customers" as const, label: "Customers", icon: <Users className="h-4 w-4" /> },
  ]

  const getCurrentData = () => {
    switch (activeTab) {
      case "samples":
        return samplesQuery.data
      case "products":
        return productsQuery.data
      case "lab-tests":
        return labTestsQuery.data
      case "customers":
        return customersQuery.data
    }
  }

  const isLoading = activeTab === "samples" ? samplesQuery.isLoading :
    activeTab === "products" ? productsQuery.isLoading :
    activeTab === "lab-tests" ? labTestsQuery.isLoading :
    customersQuery.isLoading

  const handleSampleClick = (sample: ArchivedLot) => {
    navigate(`/audittrail/lot/${sample.lot_id}/${sample.product_id}`)
  }

  const data = getCurrentData()

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "-"
    return format(new Date(dateString), "MMM d, yyyy")
  }

  const getItemName = (item: Product | LabTestType | Customer) => {
    if ("display_name" in item) return item.display_name
    if ("test_name" in item) return item.test_name
    if ("company_name" in item) return item.company_name
    return "Unknown"
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.275 }}
        className="space-y-8"
      >
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-slate-100 p-2">
            <Archive className="h-6 w-6 text-slate-600" />
          </div>
          <div>
            <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Audit Trail</h1>
            <p className="mt-0.5 text-[15px] text-slate-500">View and restore archived products, lab tests, and customers</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-slate-200 pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id)
                setPage(1)
                setSearch("")
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[14px] font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Search and Count */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder={activeTab === "samples" ? "Search completed samples..." : `Search archived ${activeTab.replace("-", " ")}...`}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="pl-10 h-11 bg-white border-slate-200 rounded-lg shadow-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 transition-shadow"
            />
          </div>
          <span className="text-[14px] font-medium text-slate-500">
            {data?.total ?? 0} {activeTab === "samples" ? "completed samples" : "archived items"}
          </span>
          {activeTab === "samples" && (
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="text-slate-400 hover:text-slate-600 transition-colors">
                    <Keyboard className="h-4 w-4" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-[12px]">
                  <div className="space-y-1">
                    <div className="font-medium text-slate-700 mb-1.5">Keyboard Shortcuts</div>
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-500">Open sample</span>
                      <kbd className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded">1-20</kbd>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>

        {/* Table */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
            </div>
          ) : data?.items.length === 0 ? (
            <EmptyState
              icon={activeTab === "samples" ? Beaker : Archive}
              title={activeTab === "samples" ? "No completed samples found" : `No archived ${activeTab.replace("-", " ")} found`}
              description={search ? "Try adjusting your search" : activeTab === "samples" ? "Released and rejected samples will appear here" : `No ${activeTab.replace("-", " ")} have been archived yet`}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                  {activeTab === "samples" && (
                    <>
                      <TableHead className="w-[40px] text-slate-400 text-[12px] font-normal">#</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Reference #</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Lot #</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Brand</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Product</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Status</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Completed</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Customer</TableHead>
                    </>
                  )}
                  {activeTab === "products" && (
                    <>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Product</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Brand</TableHead>
                    </>
                  )}
                  {activeTab === "lab-tests" && (
                    <>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Test Name</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Category</TableHead>
                    </>
                  )}
                  {activeTab === "customers" && (
                    <>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Company</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Contact</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Email</TableHead>
                    </>
                  )}
                  {activeTab !== "samples" && (
                    <>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Archived</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Reason</TableHead>
                      <TableHead className="w-[100px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
                    </>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeTab === "samples" && samplesQuery.data?.items.map((sample, index) => (
                  <TableRow
                    key={`${sample.lot_id}-${sample.product_id}`}
                    className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                    onClick={() => handleSampleClick(sample)}
                  >
                    <TableCell className="text-[12px] text-slate-400 font-mono tabular-nums">
                      {index + 1}
                    </TableCell>
                    <TableCell className="font-mono font-semibold text-slate-900 text-[14px]">
                      {sample.reference_number}
                    </TableCell>
                    <TableCell className="font-mono text-slate-700 text-[14px]">
                      {sample.lot_number}
                    </TableCell>
                    <TableCell className="text-slate-600 text-[14px]">{sample.brand}</TableCell>
                    <TableCell className="text-slate-700 text-[14px]">
                      {sample.product_name}
                      {sample.flavor && (
                        <span className="text-slate-500"> - {sample.flavor}</span>
                      )}
                      {sample.size && (
                        <span className="text-slate-400 ml-1">({sample.size})</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={sample.status === "released" ? "emerald" : "destructive"}
                        className="text-[11px]"
                      >
                        {sample.status === "released" ? "Released" : "Rejected"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {formatDate(sample.completed_at)}
                    </TableCell>
                    <TableCell className="text-slate-600 text-[14px]">
                      {sample.customer_name || "—"}
                    </TableCell>
                  </TableRow>
                ))}
                {activeTab === "products" && productsQuery.data?.items.map((product) => (
                  <TableRow key={product.id} className="hover:bg-slate-50/50 transition-colors">
                    <TableCell className="font-semibold text-slate-900 text-[14px]">
                      <div className="flex items-center gap-2">
                        {product.display_name}
                        {product.version && (
                          <Badge variant="outline" className="text-[11px]">{product.version}</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-slate-700 text-[14px]">{product.brand}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">{formatDate(product.archived_at)}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {product.archive_reason ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-help truncate max-w-[150px] inline-block">
                              {product.archive_reason.length > 30
                                ? `${product.archive_reason.substring(0, 30)}...`
                                : product.archive_reason}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[300px]">
                            <p>{product.archive_reason}</p>
                          </TooltipContent>
                        </Tooltip>
                      ) : "-"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setRestoreDialog({ type: "products", item: product })}
                        className="h-8 px-3 text-slate-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                      >
                        <RotateCcw className="h-4 w-4 mr-1.5" />
                        Restore
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {activeTab === "lab-tests" && labTestsQuery.data?.items.map((test) => (
                  <TableRow key={test.id} className="hover:bg-slate-50/50 transition-colors">
                    <TableCell className="font-semibold text-slate-900 text-[14px]">{test.test_name}</TableCell>
                    <TableCell className="text-[14px]">
                      <Badge variant="outline" className="bg-slate-50 text-slate-600">{test.test_category}</Badge>
                    </TableCell>
                    <TableCell className="text-slate-500 text-[14px]">{formatDate(test.archived_at)}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {test.archive_reason ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-help truncate max-w-[150px] inline-block">
                              {test.archive_reason.length > 30
                                ? `${test.archive_reason.substring(0, 30)}...`
                                : test.archive_reason}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[300px]">
                            <p>{test.archive_reason}</p>
                          </TooltipContent>
                        </Tooltip>
                      ) : "-"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setRestoreDialog({ type: "lab-tests", item: test })}
                        className="h-8 px-3 text-slate-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                      >
                        <RotateCcw className="h-4 w-4 mr-1.5" />
                        Restore
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {activeTab === "customers" && customersQuery.data?.items.map((customer) => (
                  <TableRow key={customer.id} className="hover:bg-slate-50/50 transition-colors">
                    <TableCell className="font-semibold text-slate-900 text-[14px]">{customer.company_name}</TableCell>
                    <TableCell className="text-slate-700 text-[14px]">{customer.contact_name}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">{customer.email}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">{formatDate(customer.archived_at)}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {customer.archive_reason ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-help truncate max-w-[150px] inline-block">
                              {customer.archive_reason.length > 30
                                ? `${customer.archive_reason.substring(0, 30)}...`
                                : customer.archive_reason}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-[300px]">
                            <p>{customer.archive_reason}</p>
                          </TooltipContent>
                        </Tooltip>
                      ) : "-"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setRestoreDialog({ type: "customers", item: customer })}
                        className="h-8 px-3 text-slate-600 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                      >
                        <RotateCcw className="h-4 w-4 mr-1.5" />
                        Restore
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total_pages >= 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">
              <p className="text-[14px] text-slate-500">
                Page {data.page} of {data.total_pages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="border-slate-200 hover:bg-slate-50 h-9"
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page === data.total_pages}
                  className="border-slate-200 hover:bg-slate-50 h-9"
                >
                  Next
                </Button>
                <Select
                  value={String(pageSize)}
                  onValueChange={(v) => {
                    setPageSize(Number(v))
                    setPage(1)
                  }}
                >
                  <SelectTrigger className="w-20 h-9 border-slate-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="20">20</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </div>

        {/* Restore Confirmation Dialog */}
        <Dialog open={!!restoreDialog} onOpenChange={() => setRestoreDialog(null)}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-[18px] font-bold text-slate-900">
                Restore Item
              </DialogTitle>
              <DialogDescription className="text-slate-500">
                Are you sure you want to restore "{restoreDialog && getItemName(restoreDialog.item)}"?
                This item will become active again and available for use.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                variant="outline"
                onClick={() => setRestoreDialog(null)}
                disabled={isRestoring}
              >
                Cancel
              </Button>
              <Button
                onClick={handleRestore}
                disabled={isRestoring}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {isRestoring ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Restoring...
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    Restore
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </motion.div>
    </div>
  )
}
