import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { Loader2, Inbox, CheckCircle2, Download, Mail, Search } from "lucide-react"
import { toast } from "sonner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useReleaseQueue, useRecentlyReleased, useDownloadCoa, useSendEmail } from "@/hooks/useRelease"
import type { ReleaseQueueItem, ArchiveItem } from "@/types/release"

export function ReleaseQueuePage() {
  const navigate = useNavigate()
  const [recentDays, setRecentDays] = useState(7)
  const [search, setSearch] = useState("")
  const [showEmailDialog, setShowEmailDialog] = useState(false)
  const [emailRecipient, setEmailRecipient] = useState("")
  const [selectedItem, setSelectedItem] = useState<ArchiveItem | null>(null)
  const { data: queue = [], isLoading } = useReleaseQueue()
  const { data: recentlyReleased = [], isLoading: isLoadingRecent } = useRecentlyReleased(recentDays)
  const downloadCoa = useDownloadCoa()
  const sendEmail = useSendEmail()

  // Filter recently released based on search
  const filteredReleased = recentlyReleased.filter((item) => {
    if (!search.trim()) return true
    const searchLower = search.toLowerCase()
    return (
      item.product_name?.toLowerCase().includes(searchLower) ||
      item.lot_number?.toLowerCase().includes(searchLower) ||
      item.reference_number?.toLowerCase().includes(searchLower) ||
      item.brand?.toLowerCase().includes(searchLower) ||
      item.customer_name?.toLowerCase().includes(searchLower)
    )
  })

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  }

  const handleRowClick = (item: ReleaseQueueItem | ArchiveItem) => {
    navigate(`/release/${item.lot_id}/${item.product_id}`)
  }

  const handleDownload = async (e: React.MouseEvent, lotId: number, productId: number) => {
    e.stopPropagation() // Prevent row click navigation
    try {
      await downloadCoa.mutateAsync({ lotId, productId })
      toast.success("COA downloaded successfully")
    } catch (error) {
      console.error("Failed to download COA:", error)
      toast.error("Failed to download COA")
    }
  }

  const handleEmailClick = (e: React.MouseEvent, item: ArchiveItem) => {
    e.stopPropagation() // Prevent row click navigation
    setSelectedItem(item)
    setEmailRecipient("")
    setShowEmailDialog(true)
  }

  const handleSendEmail = async () => {
    if (!emailRecipient.trim() || !selectedItem) return

    try {
      await sendEmail.mutateAsync({
        lotId: selectedItem.lot_id,
        productId: selectedItem.product_id,
        recipientEmail: emailRecipient.trim(),
      })
      setEmailRecipient("")
      setShowEmailDialog(false)
      setSelectedItem(null)
    } catch (error) {
      console.error("Failed to send email:", error)
    }
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.275 }}
        className="space-y-8"
      >
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

      {/* Awaiting Release Table */}
      <div className="space-y-4">
        <h2 className="text-[18px] font-semibold text-slate-900">
          Awaiting Release
        </h2>
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
                  Ref
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Lot
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Brand
                </TableHead>
                <TableHead className="text-[12px] font-semibold text-slate-600">
                  Product
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
                  <TableCell className="text-[13px] text-slate-600">
                    {item.brand}
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

      {/* Recently Released Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <h2 className="text-[18px] font-semibold text-slate-900">
            Recently Released
          </h2>
          <div className="flex-1" />
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          <Select
            value={recentDays.toString()}
            onValueChange={(value) => setRecentDays(Number(value))}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Past 7 days</SelectItem>
              <SelectItem value="30">Past 30 days</SelectItem>
              <SelectItem value="60">Past 60 days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          {isLoadingRecent ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
            </div>
          ) : filteredReleased.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16">
              <div className="rounded-xl bg-slate-100 p-4">
                <CheckCircle2 className="h-8 w-8 text-slate-400" />
              </div>
              <p className="mt-4 text-[14px] font-medium text-slate-600">
                {search.trim() ? "No matching releases found" : `No releases in the past ${recentDays} days`}
              </p>
              <p className="mt-1 text-[13px] text-slate-500">
                {search.trim() ? "Try adjusting your search" : "Released COAs will appear here"}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80">
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Ref
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Lot
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Brand
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Product
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Released Date
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Customer
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600">
                    Status
                  </TableHead>
                  <TableHead className="text-[12px] font-semibold text-slate-600 w-[180px]">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredReleased.map((item) => (
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
                    <TableCell className="text-[13px] text-slate-600">
                      {item.brand}
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
                      {formatDate(item.released_at)}
                    </TableCell>
                    <TableCell className="text-[13px] text-slate-600">
                      {item.customer_name || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="emerald" className="text-[11px]">
                        Released
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => handleDownload(e, item.lot_id, item.product_id)}
                          disabled={downloadCoa.isPending}
                          className="h-8 text-[12px]"
                        >
                          {downloadCoa.isPending ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Download className="h-3 w-3" />
                          )}
                          Download
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => handleEmailClick(e, item)}
                          className="h-8 text-[12px]"
                        >
                          <Mail className="h-3 w-3" />
                          Email
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
      </motion.div>

      {/* Email Dialog */}
      <Dialog open={showEmailDialog} onOpenChange={setShowEmailDialog}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Send COA via Email</DialogTitle>
          </DialogHeader>
          {selectedItem && (
            <div className="py-2">
              <div className="rounded-lg bg-slate-50 p-3 mb-4">
                <div className="space-y-1.5">
                  <div>
                    <p className="text-[11px] text-slate-500">Product</p>
                    <p className="text-[13px] font-medium text-slate-900">
                      {selectedItem.product_name}
                      {selectedItem.flavor && ` - ${selectedItem.flavor}`}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] text-slate-500">Lot Number</p>
                    <p className="text-[13px] font-mono font-medium text-slate-900">
                      {selectedItem.lot_number}
                    </p>
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="emailRecipient" className="text-[12px]">
                  Recipient Email
                </Label>
                <Input
                  id="emailRecipient"
                  type="email"
                  value={emailRecipient}
                  onChange={(e) => setEmailRecipient(e.target.value)}
                  placeholder="Enter recipient email"
                  autoFocus
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowEmailDialog(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSendEmail}
              disabled={!emailRecipient.trim() || sendEmail.isPending}
            >
              {sendEmail.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Send Email
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
