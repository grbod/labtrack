import { useState } from "react"
import {
  Loader2,
  FileText,
  Download,
  CheckCircle2,
  Clock,
  AlertCircle,
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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"

import { useLots, useLotStatusCounts } from "@/hooks/useLots"
import { useTestResults } from "@/hooks/useTestResults"
import type { Lot } from "@/types"

export function PublishPage() {
  const [page, setPage] = useState(1)
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  // Get approved lots ready for COA generation
  const { data: lotsData, isLoading } = useLots({
    page,
    page_size: 50,
    status: "APPROVED",
  })
  const { data: statusCounts } = useLotStatusCounts()

  const handleGenerateCOA = async (lot: Lot) => {
    setGeneratingId(lot.id)
    // Simulate COA generation (in real app, this would call an API)
    await new Promise((resolve) => setTimeout(resolve, 1500))
    alert(`COA generated for ${lot.reference_number}! (Demo - actual generation coming soon)`)
    setGeneratingId(null)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "APPROVED":
        return <CheckCircle2 className="h-4 w-4 text-green-600" />
      case "RELEASED":
        return <Download className="h-4 w-4 text-blue-600" />
      case "PENDING":
        return <Clock className="h-4 w-4 text-yellow-600" />
      default:
        return <AlertCircle className="h-4 w-4 text-gray-600" />
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Publish COA</h1>
        <p className="text-muted-foreground text-sm">
          Generate and publish Certificates of Analysis
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{statusCounts?.approved ?? 0}</div>
            <p className="text-xs text-muted-foreground">Ready to Publish</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{statusCounts?.released ?? 0}</div>
            <p className="text-xs text-muted-foreground">Released</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{statusCounts?.pending ?? 0}</div>
            <p className="text-xs text-muted-foreground">Pending</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{statusCounts?.under_review ?? 0}</div>
            <p className="text-xs text-muted-foreground">Under Review</p>
          </CardContent>
        </Card>
      </div>

      {/* Lots Ready for COA */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Lots Ready for COA Generation
          </CardTitle>
          <CardDescription>
            These lots have all test results approved and are ready to generate COAs
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Reference</TableHead>
                  <TableHead>Lot Number</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Mfg Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[150px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lotsData?.items.map((lot) => (
                  <TableRow key={lot.id}>
                    <TableCell className="font-mono font-medium">
                      {lot.reference_number}
                    </TableCell>
                    <TableCell>{lot.lot_number}</TableCell>
                    <TableCell className="capitalize text-muted-foreground">
                      {lot.lot_type.toLowerCase().replace("_", " ")}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {lot.mfg_date
                        ? new Date(lot.mfg_date).toLocaleDateString()
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5">
                        {getStatusIcon(lot.status)}
                        <span className="capitalize text-sm">
                          {lot.status.toLowerCase()}
                        </span>
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        onClick={() => handleGenerateCOA(lot)}
                        disabled={generatingId === lot.id}
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
                {lotsData?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No lots ready for COA generation
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {lotsData && lotsData.total_pages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Page {lotsData.page} of {lotsData.total_pages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(lotsData.total_pages, p + 1))}
                  disabled={page === lotsData.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
