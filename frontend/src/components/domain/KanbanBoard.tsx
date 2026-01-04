import { useState, useMemo } from "react"
import { cn } from "@/lib/utils"
import type { Lot, LotStatus } from "@/types"

/**
 * Kanban column configuration
 * Maps each column to its status (or special "recently_completed" identifier)
 */
interface KanbanColumnConfig {
  id: LotStatus | "recently_completed"
  label: string
}

// Base columns without the dynamic Recently Completed label
const BASE_KANBAN_COLUMNS: KanbanColumnConfig[] = [
  { id: "awaiting_results", label: "Awaiting Results" },
  { id: "partial_results", label: "Partial Results" },
  { id: "under_review", label: "In Review" },
  { id: "awaiting_release", label: "Awaiting Release" },
  { id: "rejected", label: "Rejected" },
]

const CARDS_PER_COLUMN = 8

interface KanbanBoardProps {
  lots: Lot[]
  onCardClick: (lot: Lot) => void
  staleWarningDays?: number
  staleCriticalDays?: number
  recentlyCompletedDays?: number
}

/**
 * Determines staleness level of a lot based on its age
 */
type StalenessLevel = "critical" | "warning" | "normal"

function calculateStaleness(
  lot: Lot,
  warningDays: number,
  criticalDays: number
): { level: StalenessLevel; daysOld: number } {
  const createdAt = new Date(lot.created_at)
  const now = new Date()
  const diffTime = now.getTime() - createdAt.getTime()
  const daysOld = Math.floor(diffTime / (1000 * 60 * 60 * 24))

  if (daysOld >= criticalDays) {
    return { level: "critical", daysOld }
  }
  if (daysOld >= warningDays) {
    return { level: "warning", daysOld }
  }
  return { level: "normal", daysOld }
}

/**
 * Formats lot type for display
 */
function formatLotType(lotType: string): string {
  return lotType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

/**
 * Individual Kanban card component
 */
interface KanbanCardProps {
  lot: Lot
  staleness: { level: StalenessLevel; daysOld: number }
  onClick: () => void
  isCompleted?: boolean
}

function KanbanCard({ lot, staleness, onClick, isCompleted = false }: KanbanCardProps) {
  const borderClass = {
    critical: "border-red-400 border-l-4",
    warning: "border-orange-400 border-l-4",
    normal: "border-slate-200",
  }[staleness.level]

  // Get days badge configuration based on staleness
  const getDaysBadge = () => {
    if (isCompleted) {
      const completedAt = lot.updated_at ? new Date(lot.updated_at) : new Date(lot.created_at)
      const daysSinceCompletion = Math.floor(
        (Date.now() - completedAt.getTime()) / (1000 * 60 * 60 * 24)
      )
      return { days: daysSinceCompletion, color: "bg-emerald-100 text-emerald-700" }
    }

    const colorMap = {
      critical: "bg-red-100 text-red-700",
      warning: "bg-orange-100 text-orange-700",
      normal: "bg-slate-100 text-slate-600",
    }
    return { days: staleness.daysOld, color: colorMap[staleness.level] }
  }

  const daysBadge = getDaysBadge()

  // Get first product for display
  const product = lot.products?.[0] ?? null
  const hasMultipleProducts = (lot.products?.length ?? 0) > 1

  return (
    <div
      onClick={onClick}
      className={cn(
        "cursor-pointer rounded-lg border bg-white p-2.5 shadow-sm transition-all",
        "hover:border-slate-300 hover:shadow",
        isCompleted ? "border-slate-200" : borderClass
      )}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          onClick()
        }
      }}
    >
      {/* Product info or lot type fallback */}
      {product ? (
        <>
          {/* Line 1: Brand + Days Badge */}
          <div className="flex items-start justify-between gap-2">
            <p className="text-[12px] font-semibold text-slate-900 truncate">
              {product.brand}
            </p>
            <span
              className={cn(
                "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[9px] font-semibold",
                daysBadge.color
              )}
            >
              {daysBadge.days}d
            </span>
          </div>
          {/* Line 2: Product Name */}
          <p className="text-[11px] text-slate-700 truncate">
            {product.product_name}
          </p>
          {/* Line 3: Flavor only (no size) */}
          {product.flavor && (
            <p className="text-[10px] text-slate-500 truncate">
              {product.flavor}
            </p>
          )}
          {/* Multi-product indicator */}
          {hasMultipleProducts && (
            <p className="text-[9px] text-blue-500 font-medium">
              +{lot.products!.length - 1} more product{lot.products!.length > 2 ? "s" : ""}
            </p>
          )}
        </>
      ) : (
        <div className="flex items-start justify-between gap-2">
          <p className="text-[12px] font-semibold text-slate-900 truncate">
            {formatLotType(lot.lot_type)}
          </p>
          <span
            className={cn(
              "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[9px] font-semibold",
              daysBadge.color
            )}
          >
            {daysBadge.days}d
          </span>
        </div>
      )}

      {/* Footer: Lab Ref + Tests Badge */}
      <div className="mt-1.5 flex items-center justify-between">
        <p className="text-[11px] text-slate-600">
          Lab Ref <span className="font-mono font-medium">{lot.reference_number}</span>
        </p>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-medium text-slate-500">
          0/0
        </span>
      </div>
    </div>
  )
}

/**
 * Individual Kanban column component
 */
interface KanbanColumnProps {
  config: KanbanColumnConfig
  lots: Array<Lot & { staleness: { level: StalenessLevel; daysOld: number } }>
  onCardClick: (lot: Lot) => void
}

function KanbanColumn({ config, lots, onCardClick }: KanbanColumnProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isCompletedColumn = config.id === "recently_completed"

  const displayedLots = isExpanded ? lots : lots.slice(0, CARDS_PER_COLUMN)
  const hiddenCount = lots.length - CARDS_PER_COLUMN
  const showExpandButton = !isExpanded && hiddenCount > 0

  return (
    <div className="flex flex-col">
      {/* Column Header */}
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-[13px] font-semibold text-slate-700">{config.label}</h3>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
          {lots.length}
        </span>
      </div>

      {/* Column Cards Container */}
      <div className="flex-1 space-y-2 rounded-lg bg-slate-50/50 p-2 min-h-[200px]">
        {lots.length === 0 ? (
          <p className="py-8 text-center text-[12px] text-slate-400">No samples</p>
        ) : (
          <>
            {displayedLots.map((lot) => (
              <KanbanCard
                key={lot.id}
                lot={lot}
                staleness={lot.staleness}
                onClick={() => onCardClick(lot)}
                isCompleted={isCompletedColumn}
              />
            ))}
            {showExpandButton && (
              <button
                onClick={() => setIsExpanded(true)}
                className="w-full rounded-lg py-2 text-[12px] font-medium text-blue-600 hover:bg-blue-50 transition-colors"
              >
                +{hiddenCount} more
              </button>
            )}
            {isExpanded && lots.length > CARDS_PER_COLUMN && (
              <button
                onClick={() => setIsExpanded(false)}
                className="w-full rounded-lg py-2 text-[12px] font-medium text-slate-500 hover:bg-slate-100 transition-colors"
              >
                Show less
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/**
 * KanbanBoard displays lots organized by status in columns.
 *
 * Features:
 * - 6 columns: Awaiting Results, Partial Results, In Review, Awaiting Release, Rejected, Recently Completed
 * - Stale items bubble to top with visual indicators (red/orange borders, warning icons)
 * - Maximum 8 cards per column with "+X more" button to expand
 * - Click cards to trigger onCardClick callback
 */
export function KanbanBoard({
  lots,
  onCardClick,
  staleWarningDays = 7,
  staleCriticalDays = 12,
  recentlyCompletedDays = 7,
}: KanbanBoardProps) {
  // Build columns with dynamic Recently Completed label
  const kanbanColumns = useMemo((): KanbanColumnConfig[] => [
    ...BASE_KANBAN_COLUMNS,
    { id: "recently_completed", label: `Recently Completed (${recentlyCompletedDays}d)` },
  ], [recentlyCompletedDays])

  /**
   * Process and organize lots by column with staleness information
   */
  const columnData = useMemo(() => {
    const now = new Date()
    const recentlyCompletedCutoff = new Date()
    recentlyCompletedCutoff.setDate(now.getDate() - recentlyCompletedDays)

    // Group lots by status with staleness calculation
    const groupedLots: Record<
      string,
      Array<Lot & { staleness: { level: StalenessLevel; daysOld: number } }>
    > = {}

    // Initialize all columns
    kanbanColumns.forEach((col) => {
      groupedLots[col.id] = []
    })

    lots.forEach((lot) => {
      const staleness = calculateStaleness(lot, staleWarningDays, staleCriticalDays)
      const lotWithStaleness = { ...lot, staleness }

      // Handle "approved" status - only show in recently_completed if within 7 days
      if (lot.status === "approved") {
        const updatedAt = lot.updated_at ? new Date(lot.updated_at) : new Date(lot.created_at)
        if (updatedAt >= recentlyCompletedCutoff) {
          groupedLots["recently_completed"].push(lotWithStaleness)
        }
        // Skip approved lots older than 7 days
        return
      }

      // Handle "released" status - don't show in kanban
      if (lot.status === "released") {
        return
      }

      // Add lot to its status column
      if (groupedLots[lot.status]) {
        groupedLots[lot.status].push(lotWithStaleness)
      }
    })

    // Sort each column: critical first, then warning, then normal
    // Within each staleness level, sort by age (oldest first)
    Object.keys(groupedLots).forEach((status) => {
      groupedLots[status].sort((a, b) => {
        const levelOrder = { critical: 0, warning: 1, normal: 2 }
        const levelDiff = levelOrder[a.staleness.level] - levelOrder[b.staleness.level]
        if (levelDiff !== 0) return levelDiff
        // Within same level, sort by age (older items first)
        return b.staleness.daysOld - a.staleness.daysOld
      })
    })

    return groupedLots
  }, [lots, staleWarningDays, staleCriticalDays, recentlyCompletedDays, kanbanColumns])

  return (
    <div className="grid grid-cols-6 gap-4">
      {kanbanColumns.map((column) => (
        <KanbanColumn
          key={column.id}
          config={column}
          lots={columnData[column.id] || []}
          onCardClick={onCardClick}
        />
      ))}
    </div>
  )
}
