import { useState } from "react"
import { ChevronLeft, ChevronRight, ChevronDown, X, Package, Lock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import type { LotWithProductSpecs, LotStatus } from "@/types"

/** Status label configuration */
const STATUS_CONFIG: Record<LotStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  awaiting_results: { label: "Awaiting Results", variant: "secondary" },
  partial_results: { label: "Partial Results", variant: "secondary" },
  under_review: { label: "In Review", variant: "default" },
  awaiting_release: { label: "Awaiting Release", variant: "default" },
  approved: { label: "Approved", variant: "outline" },
  released: { label: "Released", variant: "outline" },
  rejected: { label: "Rejected", variant: "destructive" },
}

interface SampleModalHeaderProps {
  /** Lot with product specs */
  lot: LotWithProductSpecs
  /** Whether this lot is locked (approved/released) */
  isLocked: boolean
  /** Whether prev navigation is disabled */
  prevDisabled: boolean
  /** Whether next navigation is disabled */
  nextDisabled: boolean
  /** Callback to navigate to prev/next sample */
  onNavigate: (direction: "prev" | "next") => void
  /** Callback to close the modal */
  onClose: () => void
}

/**
 * Modal header with product display, navigation, and status.
 * Shows product name for single product, "MULTI-SKU" with collapsible list for multi-SKU.
 */
export function SampleModalHeader({
  lot,
  isLocked,
  prevDisabled,
  nextDisabled,
  onNavigate,
  onClose,
}: SampleModalHeaderProps) {
  const [isProductsExpanded, setIsProductsExpanded] = useState(false)

  const isMultiSku = lot.lot_type === "multi_sku_composite"
  const primaryProduct = lot.products[0]
  const statusConfig = STATUS_CONFIG[lot.status] || { label: lot.status, variant: "secondary" as const }

  return (
    <DialogHeader className="flex-shrink-0 border-b border-slate-200 pb-4">
      <div className="flex items-center justify-between">
        {/* Left: Prev button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onNavigate("prev")}
          disabled={prevDisabled}
          className="text-slate-400 hover:text-slate-600 disabled:opacity-30"
          aria-label="Previous sample"
        >
          <ChevronLeft className="h-5 w-5" />
        </Button>

        {/* Center: Title section */}
        <div className="flex-1 text-center px-4">
          {/* Main title */}
          <DialogTitle className="text-xl font-semibold text-slate-900">
            {isMultiSku ? (
              <span className="flex items-center justify-center gap-2">
                <Package className="h-5 w-5 text-slate-500" />
                MULTI-SKU
              </span>
            ) : primaryProduct ? (
              primaryProduct.display_name
            ) : (
              <span className="text-slate-400 italic">No product assigned</span>
            )}
          </DialogTitle>

          {/* Multi-SKU collapsible product list */}
          {isMultiSku && lot.products.length > 0 && (
            <Collapsible open={isProductsExpanded} onOpenChange={setIsProductsExpanded}>
              <CollapsibleTrigger className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mt-1 mx-auto">
                {lot.products.length} products
                <ChevronDown
                  className={cn(
                    "h-4 w-4 transition-transform duration-200",
                    isProductsExpanded && "rotate-180"
                  )}
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <div className="space-y-1 text-sm text-slate-600">
                  {lot.products.map((product) => (
                    <div
                      key={product.id}
                      className="flex items-center justify-center gap-2"
                    >
                      <span>{product.display_name}</span>
                      {product.percentage && (
                        <span className="text-xs text-slate-400">
                          ({product.percentage}%)
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Sub-info: Lot number, Reference number, Status badge */}
          {/* Note: Using div instead of DialogDescription to avoid <p> containing <div> hydration error */}
          <div className="mt-2 flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <span className="font-mono text-slate-600">{lot.lot_number}</span>
            <span className="text-slate-300">|</span>
            <span className="text-slate-600">{lot.reference_number}</span>
            <span className="text-slate-300">|</span>
            <Badge variant={statusConfig.variant}>
              {isLocked && <Lock className="h-3 w-3 mr-1" />}
              {statusConfig.label}
            </Badge>
          </div>
        </div>

        {/* Right: Next + Close buttons */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onNavigate("next")}
            disabled={nextDisabled}
            className="text-slate-400 hover:text-slate-600 disabled:opacity-30"
            aria-label="Next sample"
          >
            <ChevronRight className="h-5 w-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </DialogHeader>
  )
}
