import { useState } from "react"
import { FlaskConical, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useProductTestSpecs } from "@/hooks/useProducts"

interface TestSpecsTooltipProps {
  productId: number
  onClick: () => void
}

const MAX_VISIBLE_TESTS = 5

export function TestSpecsTooltip({ productId, onClick }: TestSpecsTooltipProps) {
  const [isOpen, setIsOpen] = useState(false)

  // Only fetch when tooltip is open
  const { data: testSpecs, isLoading } = useProductTestSpecs(isOpen ? productId : 0)

  const visibleTests = testSpecs?.slice(0, MAX_VISIBLE_TESTS) ?? []
  const remainingCount = (testSpecs?.length ?? 0) - MAX_VISIBLE_TESTS

  return (
    <TooltipProvider>
      <Tooltip open={isOpen} onOpenChange={setIsOpen} delayDuration={300}>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClick}
            className="h-8 w-8 p-0 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
          >
            <FlaskConical className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left" className="max-w-[250px] p-0">
          <div className="px-3 py-2">
            {isLoading ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span className="text-xs">Loading...</span>
              </div>
            ) : testSpecs?.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No tests configured</p>
            ) : (
              <div className="space-y-1">
                <p className="text-xs font-semibold text-slate-700 mb-1.5">
                  Test Specifications
                </p>
                <ul className="space-y-0.5">
                  {visibleTests.map((spec) => (
                    <li key={spec.id} className="text-xs text-slate-600">
                      {spec.is_required ? (
                        <span className="font-semibold">{spec.test_name} *</span>
                      ) : (
                        <span>{spec.test_name}</span>
                      )}
                    </li>
                  ))}
                </ul>
                {remainingCount > 0 && (
                  <p className="text-xs text-slate-400 mt-1">
                    ...and {remainingCount} more
                  </p>
                )}
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
