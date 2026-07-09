import { useState, useEffect, useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { ClipboardList, Loader2 } from "lucide-react"

import { useLots, useAllLots } from "@/hooks/useLots"
import { useSystemSettings } from "@/hooks/useSettings"
import { KanbanBoard } from "@/components/domain/KanbanBoard"
import { SampleTable } from "@/components/domain/SampleTable"
import { SampleModal } from "@/components/domain/SampleModal"
import type { Lot } from "@/types"

export function SampleTrackerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const highlightRef = searchParams.get('highlight')

  // Clear highlight param from URL after animation completes (2s)
  useEffect(() => {
    if (highlightRef) {
      const timer = setTimeout(() => {
        setSearchParams({}, { replace: true })
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [highlightRef, setSearchParams])

  const [selectedLot, setSelectedLot] = useState<Lot | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [scrollToRetests, setScrollToRetests] = useState(false)

  // Active workflow statuses only (exclude approved/released/awaiting_release/
  // rejected — those live in the Release Queue / Archive).
  const EXCLUDED_STATUSES = useMemo(
    () => ["approved", "released", "awaiting_release", "rejected"] as const,
    []
  )

  // Kanban board: accumulate ALL active lots (no 100-row cap) so the board and
  // its column counts are complete.
  const { data: allLotsData, isLoading } = useAllLots({
    exclude_statuses: [...EXCLUDED_STATUSES],
  })

  // Table view: real server-side pagination + search + status filter.
  const [tablePage, setTablePage] = useState(1)
  const [tablePageSize, setTablePageSize] = useState(25)
  const [tableSearchInput, setTableSearchInput] = useState("")
  const [tableSearch, setTableSearch] = useState("")
  const [tableStatus, setTableStatus] = useState("all")

  // Debounce the table search box before it hits the server.
  useEffect(() => {
    const timer = setTimeout(() => {
      setTableSearch(tableSearchInput)
      setTablePage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [tableSearchInput])

  const { data: tableData, isFetching: isTableFetching, isLoading: isTableLoading } = useLots({
    page: tablePage,
    page_size: tablePageSize,
    search: tableSearch || undefined,
    // Always scope to active lots; the status dropdown narrows within them.
    status: tableStatus === "all" ? undefined : (tableStatus as Lot["status"]),
    exclude_statuses: [...EXCLUDED_STATUSES],
  })

  // The full active list backs modal prev/next navigation.
  const navLots = allLotsData?.items ?? []

  // Get stale thresholds from system settings
  const { settings: systemSettings } = useSystemSettings()

  const handleCardClick = (lot: Lot) => {
    setSelectedLot(lot)
    setIsModalOpen(true)
  }

  const handleRetestSubRowClick = (lot: Lot) => {
    setSelectedLot(lot)
    setScrollToRetests(true)
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setSelectedLot(null)
    setScrollToRetests(false)
  }

  // After submission, navigate to next under_review sample or close
  const handleSubmitSuccess = () => {
    if (!selectedLot || navLots.length === 0) {
      handleCloseModal()
      return
    }

    // Find next under_review sample (excluding the one just submitted)
    const currentIndex = navLots.findIndex(l => l.id === selectedLot.id)

    // Look forward first, then wrap around
    for (let i = 1; i < navLots.length; i++) {
      const idx = (currentIndex + i) % navLots.length
      if (navLots[idx].status === "under_review") {
        setSelectedLot(navLots[idx])
        return
      }
    }

    // No more under_review samples - close modal
    handleCloseModal()
  }

  const handleNavigate = (direction: "prev" | "next") => {
    if (!selectedLot || navLots.length === 0) return
    const currentIndex = navLots.findIndex(l => l.id === selectedLot.id)
    const totalItems = navLots.length

    // Loop around when reaching ends
    if (direction === "prev") {
      const newIndex = currentIndex <= 0 ? totalItems - 1 : currentIndex - 1
      setSelectedLot(navLots[newIndex])
    } else {
      const newIndex = currentIndex >= totalItems - 1 ? 0 : currentIndex + 1
      setSelectedLot(navLots[newIndex])
    }
  }

  // Navigation is never disabled when looping (except if only 1 item)
  const hasMultipleItems = navLots.length > 1
  const prevDisabled = !hasMultipleItems
  const nextDisabled = !hasMultipleItems

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Sample Tracker</h1>
          <p className="mt-1.5 text-[15px] text-slate-500">
            Track your submitted samples through the workflow
          </p>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : (
          <>
            <div className="mb-3 flex justify-end">
              <span className="text-xs text-slate-400">
                {allLotsData?.total ?? 0} active sample{(allLotsData?.total ?? 0) !== 1 ? "s" : ""}
              </span>
            </div>
            <KanbanBoard
              lots={allLotsData?.items || []}
              onCardClick={handleCardClick}
              staleWarningDays={systemSettings.staleWarningDays}
              staleCriticalDays={systemSettings.staleCriticalDays}
              highlightRef={highlightRef}
            />
          </>
        )}
      </div>

      {/* Table View Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-slate-600" />
          <h2 className="text-[15px] font-semibold text-slate-900">All Samples</h2>
        </div>

        {isTableLoading ? (
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
            </div>
          </div>
        ) : (
          <SampleTable
            lots={tableData?.items || []}
            onRowClick={handleCardClick}
            onRetestSubRowClick={handleRetestSubRowClick}
            staleWarningDays={systemSettings.staleWarningDays}
            staleCriticalDays={systemSettings.staleCriticalDays}
            total={tableData?.total ?? 0}
            page={tablePage}
            pageSize={tablePageSize}
            totalPages={tableData?.total_pages ?? 0}
            onPageChange={setTablePage}
            onPageSizeChange={(size) => {
              setTablePageSize(size)
              setTablePage(1)
            }}
            search={tableSearchInput}
            onSearchChange={setTableSearchInput}
            statusFilter={tableStatus}
            onStatusChange={(value) => {
              setTableStatus(value)
              setTablePage(1)
            }}
            isFetching={isTableFetching}
          />
        )}
      </div>

      {/* Sample Modal */}
      <SampleModal
        lot={selectedLot}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onNavigate={handleNavigate}
        prevDisabled={prevDisabled}
        nextDisabled={nextDisabled ?? false}
        onSubmitSuccess={handleSubmitSuccess}
        scrollToRetests={scrollToRetests}
      />
      </div>
    </div>
  )
}
