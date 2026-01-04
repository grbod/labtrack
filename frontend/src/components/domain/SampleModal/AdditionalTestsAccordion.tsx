import { useState, useMemo } from "react"
import { ChevronDown, Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import { TestResultsTable } from "./TestResultsTable"
import type { TestResultRow, LabTestType } from "@/types"

interface AdditionalTestsAccordionProps {
  /** Additional test results (ad-hoc, not from product specs) */
  additionalTests: TestResultRow[]
  /** Available lab test types for autocomplete */
  labTestTypes: LabTestType[]
  /** Callback when a result is updated */
  onUpdateResult: (id: number, field: string, value: string) => Promise<void>
  /** Callback when a new test is added */
  onAddTest: (testName: string, labTestTypeId: number) => Promise<void>
  /** Whether the accordion is disabled */
  disabled?: boolean
  /** ID of the row currently being saved */
  savingRowId?: number | null
}

/**
 * Collapsible accordion for additional (ad-hoc) tests.
 * Shows inline add row with autocomplete from LabTestType catalog.
 */
export function AdditionalTestsAccordion({
  additionalTests,
  labTestTypes,
  onUpdateResult,
  onAddTest,
  disabled = false,
  savingRowId,
}: AdditionalTestsAccordionProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isAddingTest, setIsAddingTest] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  // Filter lab test types based on search
  const filteredLabTestTypes = useMemo(() => {
    if (!searchQuery.trim()) {
      return labTestTypes.slice(0, 10)
    }
    const query = searchQuery.toLowerCase()
    return labTestTypes
      .filter(
        (lt) =>
          lt.test_name.toLowerCase().includes(query) ||
          lt.test_category?.toLowerCase().includes(query)
      )
      .slice(0, 10)
  }, [labTestTypes, searchQuery])

  // Handle selecting a test to add
  const handleSelectTest = async (labTestType: LabTestType) => {
    await onAddTest(labTestType.test_name, labTestType.id)
    setIsAddingTest(false)
    setSearchQuery("")
  }

  return (
    <Collapsible open={isExpanded} onOpenChange={setIsExpanded} className="mt-4">
      <CollapsibleTrigger
        className={cn(
          "flex items-center justify-between w-full px-4 py-3 rounded-lg transition-colors",
          "bg-slate-50 hover:bg-slate-100",
          isExpanded && "rounded-b-none"
        )}
      >
        <span className="text-sm font-medium text-slate-700">
          Additional Tests ({additionalTests.length})
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-slate-500 transition-transform duration-200",
            isExpanded && "rotate-180"
          )}
        />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="border border-t-0 border-slate-200 rounded-b-lg overflow-hidden">
          {/* Additional tests table */}
          {additionalTests.length > 0 && (
            <TestResultsTable
              testResults={additionalTests}
              productSpecs={[]}
              onUpdateResult={onUpdateResult}
              disabled={disabled}
              savingRowId={savingRowId}
            />
          )}

          {/* Add test row */}
          {!disabled && (
            <div className="border-t border-slate-200 p-3 bg-slate-50/50">
              {isAddingTest ? (
                <div className="flex items-start gap-2">
                  <div className="relative flex-1">
                    <Input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search test types..."
                      autoFocus
                      className="h-9"
                    />
                    {/* Autocomplete dropdown */}
                    {searchQuery && filteredLabTestTypes.length > 0 && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg z-20 max-h-[200px] overflow-y-auto">
                        {filteredLabTestTypes.map((lt) => (
                          <button
                            key={lt.id}
                            onClick={() => handleSelectTest(lt)}
                            className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm transition-colors"
                          >
                            <span className="font-medium text-slate-900">
                              {lt.test_name}
                            </span>
                            {lt.test_category && (
                              <span className="text-slate-400 ml-2">
                                ({lt.test_category})
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                    {searchQuery && filteredLabTestTypes.length === 0 && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg z-20 p-3 text-sm text-slate-500">
                        No matching test types found
                      </div>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsAddingTest(false)
                      setSearchQuery("")
                    }}
                    className="text-slate-500"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsAddingTest(true)}
                  className="text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                >
                  <Plus className="h-4 w-4 mr-1.5" />
                  Add Test
                </Button>
              )}
            </div>
          )}

          {/* Empty state */}
          {additionalTests.length === 0 && !isAddingTest && (
            <div className="py-6 text-center text-sm text-slate-400">
              No additional tests added
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
