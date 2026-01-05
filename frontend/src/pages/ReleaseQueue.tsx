import { useNavigate } from "react-router-dom"
import { Loader2, Inbox } from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { useReleaseQueue } from "@/hooks/useRelease"
import type { ReleaseQueueItem } from "@/types/release"

export function ReleaseQueuePage() {
  const navigate = useNavigate()
  const { data: queue = [], isLoading } = useReleaseQueue()

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  }

  const handleRowClick = (item: ReleaseQueueItem) => {
    navigate(`/release/${item.lot_id}/${item.product_id}`)
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">
            Release Queue
          </h1>
          <p className="mt-1.5 text-[15px] text-slate-500">
            COAs awaiting final approval and release
          </p>
        </div>
      </div>

      {/* Queue Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : queue.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="rounded-xl bg-slate-100 p-4">
              <Inbox className="h-8 w-8 text-slate-400" />
            </div>
            <p className="mt-4 text-[14px] font-medium text-slate-600">
              No COAs awaiting release
            </p>
            <p className="mt-1 text-[13px] text-slate-500">
              Approved samples will appear here for final release
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80">
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Reference #
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Lot #
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Product
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Brand
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Created Date
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Status
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((item) => (
                <TableRow
                  key={`${item.lot_id}-${item.product_id}`}
                  className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                  onClick={() => handleRowClick(item)}
                >
                  <TableCell className="font-mono text-[13px] font-medium text-slate-900">
                    {item.reference_number}
                  </TableCell>
                  <TableCell className="font-mono text-[13px] text-slate-700">
                    {item.lot_number}
                  </TableCell>
                  <TableCell className="text-[13px] text-slate-700">
                    {item.product_name}
                    {item.flavor && (
                      <span className="text-slate-500"> - {item.flavor}</span>
                    )}
                    {item.size && (
                      <span className="text-slate-400 ml-1">({item.size})</span>
                    )}
                  </TableCell>
                  <TableCell className="text-[13px] text-slate-600">
                    {item.brand}
                  </TableCell>
                  <TableCell className="text-[13px] text-slate-600">
                    {formatDate(item.created_at)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="amber" className="text-[11px]">
                      Awaiting Release
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}
