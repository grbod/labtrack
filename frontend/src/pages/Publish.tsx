import { useState } from "react"
import {
  Loader2,
  FileText,
  Download,
  CheckCircle2,
  Clock,
  AlertCircle,
  Send,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

import { useLots, useLotStatusCounts } from "@/hooks/useLots"
import type { Lot } from "@/types"

export function PublishPage() {
  const [page, setPage] = useState(1)
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  const { data: lotsData, isLoading } = useLots({
    page,
    page_size: 50,
    status: "APPROVED",
  })
  const { data: statusCounts } = useLotStatusCounts()

  const handleGenerateCOA = async (lot: Lot) => {
    setGeneratingId(lot.id)
    await new Promise((resolve) => setTimeout(resolve, 1500))
    alert(`COA generated for ${lot.reference_number}! (Demo - actual generation coming soon)`)
    setGeneratingId(null)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "APPROVED":
        return <CheckCircle2 className="h-4 w-4 text-emerald-600" />
      case "RELEASED":
        return <Download className="h-4 w-4 text-blue-600" />
      case "PENDING":
        return <Clock className="h-4 w-4 text-amber-600" />
      default:
        return <AlertCircle className="h-4 w-4 text-slate-500" />
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Publish COA</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Generate and publish Certificates of Analysis
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_0_rgba(0,0,0,0.05)] transition-shadow duration-200">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-emerald-50 p-3 shadow-sm">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">{statusCounts?.approved ?? 0}</p>
              <p className="mt-1 text-[13px] text-slate-500">Ready to Publish</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_0_rgba(0,0,0,0.05)] transition-shadow duration-200">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-blue-50 p-3 shadow-sm">
              <Send className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">{statusCounts?.released ?? 0}</p>
              <p className="mt-1 text-[13px] text-slate-500">Released</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_0_rgba(0,0,0,0.05)] transition-shadow duration-200">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-amber-50 p-3 shadow-sm">
              <Clock className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">{statusCounts?.pending ?? 0}</p>
              <p className="mt-1 text-[13px] text-slate-500">Pending</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_0_rgba(0,0,0,0.05)] transition-shadow duration-200">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-violet-50 p-3 shadow-sm">
              <AlertCircle className="h-5 w-5 text-violet-600" />
            </div>
            <div>
              <p className="text-[28px] font-bold text-slate-900 leading-none">{statusCounts?.under_review ?? 0}</p>
              <p className="mt-1 text-[13px] text-slate-500">Under Review</p>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        <div className="border-b border-slate-100 px-6 py-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-slate-600" />
            <h2 className="text-[15px] font-semibold text-slate-900">Lots Ready for COA Generation</h2>
          </div>
          <p className="mt-1 text-[13px] text-slate-500">
            These lots have all test results approved and are ready to generate COAs
          </p>
        </div>
        <div>
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
            </div>
          ) : lotsData?.items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center">
                <FileText className="h-8 w-8 text-slate-400" />
              </div>
              <p className="mt-5 text-[15px] font-medium text-slate-600">No lots ready for COA generation</p>
              <p className="mt-1 text-[14px] text-slate-500">Approved lots will appear here</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                  <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Reference</TableHead>
                  <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Lot Number</TableHead>
                  <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Type</TableHead>
                  <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Mfg Date</TableHead>
                  <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Status</TableHead>
                  <TableHead className="w-[150px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lotsData?.items.map((lot) => (
                  <TableRow key={lot.id} className="hover:bg-slate-50/50 transition-colors">
                    <TableCell className="font-mono text-[13px] font-semibold text-slate-900 tracking-wide">
                      {lot.reference_number}
                    </TableCell>
                    <TableCell className="text-slate-700 text-[14px]">{lot.lot_number}</TableCell>
                    <TableCell className="text-slate-500 text-[14px] capitalize">
                      {lot.lot_type.toLowerCase().replace("_", " ")}
                    </TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {lot.mfg_date ? new Date(lot.mfg_date).toLocaleDateString() : "-"}
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-emerald-100 text-emerald-700">
                        {getStatusIcon(lot.status)}
                        <span className="capitalize">{lot.status.toLowerCase()}</span>
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        onClick={() => handleGenerateCOA(lot)}
                        disabled={generatingId === lot.id}
                        className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-9"
                      >
                        {generatingId === lot.id ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <FileText className="mr-2 h-4 w-4" />
                        )}
                        Generate COA
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {lotsData && lotsData.total_pages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">
              <p className="text-[14px] text-slate-500">
                Page {lotsData.page} of {lotsData.total_pages}
              </p>
              <div className="flex gap-2">
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
                  onClick={() => setPage((p) => Math.min(lotsData.total_pages, p + 1))}
                  disabled={page === lotsData.total_pages}
                  className="border-slate-200 hover:bg-slate-50 h-9"
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
