import { useState } from "react"
import { useForm, useFieldArray } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import {
  Plus,
  Loader2,
  FileText,
  Trash2,
  Upload,
  ClipboardList,
  Search,
} from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

import { useLots } from "@/hooks/useLots"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import { useBulkCreateTestResults } from "@/hooks/useTestResults"
import type { Lot, LabTestType } from "@/types"

const testResultSchema = z.object({
  test_type: z.string().min(1, "Test type is required"),
  result_value: z.string().optional(),
  unit: z.string().optional(),
  specification: z.string().optional(),
  method: z.string().optional(),
  test_date: z.string().optional(),
  notes: z.string().optional(),
})

const formSchema = z.object({
  lot_id: z.number().min(1, "Please select a lot"),
  results: z.array(testResultSchema).min(1, "Add at least one test result"),
})

type FormData = z.infer<typeof formSchema>

export function ImportResultsPage() {
  const navigate = useNavigate()
  const [isLotDialogOpen, setIsLotDialogOpen] = useState(false)
  const [isTestTypeDialogOpen, setIsTestTypeDialogOpen] = useState(false)
  const [selectedLot, setSelectedLot] = useState<Lot | null>(null)
  const [lotSearch, setLotSearch] = useState("")
  const [testTypeSearch, setTestTypeSearch] = useState("")
  const [activeResultIndex, setActiveResultIndex] = useState<number | null>(null)

  const { data: lotsData } = useLots({ page_size: 100 })
  const { data: testTypesData } = useLabTestTypes({ page_size: 100, is_active: true })
  const bulkCreateMutation = useBulkCreateTestResults()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      lot_id: 0,
      results: [],
    },
  })

  const { register, handleSubmit, control, setValue, watch, formState: { errors } } = form
  const { fields, append, remove } = useFieldArray({
    control,
    name: "results",
  })

  const watchedResults = watch("results")

  const selectLot = (lot: Lot) => {
    setSelectedLot(lot)
    setValue("lot_id", lot.id)
    setIsLotDialogOpen(false)
    setLotSearch("")
  }

  const addTestType = (testType: LabTestType) => {
    if (activeResultIndex !== null) {
      setValue(`results.${activeResultIndex}.test_type`, testType.test_name)
      setValue(`results.${activeResultIndex}.unit`, testType.default_unit || "")
      setValue(`results.${activeResultIndex}.method`, testType.test_method || "")
      setValue(`results.${activeResultIndex}.specification`, testType.default_specification || "")
    } else {
      append({
        test_type: testType.test_name,
        result_value: "",
        unit: testType.default_unit || "",
        specification: testType.default_specification || "",
        method: testType.test_method || "",
        test_date: "",
        notes: "",
      })
    }
    setIsTestTypeDialogOpen(false)
    setTestTypeSearch("")
    setActiveResultIndex(null)
  }

  const addBlankResult = () => {
    append({
      test_type: "",
      result_value: "",
      unit: "",
      specification: "",
      method: "",
      test_date: "",
      notes: "",
    })
  }

  const openTestTypeSelector = (index: number | null = null) => {
    setActiveResultIndex(index)
    setIsTestTypeDialogOpen(true)
  }

  const onSubmit = async (data: FormData) => {
    try {
      await bulkCreateMutation.mutateAsync({
        lot_id: data.lot_id,
        results: data.results.map((r) => ({
          test_type: r.test_type,
          result_value: r.result_value || undefined,
          unit: r.unit || undefined,
          specification: r.specification || undefined,
          method: r.method || undefined,
          test_date: r.test_date || undefined,
          notes: r.notes || undefined,
        })),
      })
      navigate("/approvals")
    } catch {
      // Error handled by mutation
    }
  }

  const filteredLots = lotsData?.items.filter(
    (lot) =>
      lot.lot_number.toLowerCase().includes(lotSearch.toLowerCase()) ||
      lot.reference_number.toLowerCase().includes(lotSearch.toLowerCase())
  )

  const filteredTestTypes = testTypesData?.items.filter(
    (tt) =>
      tt.test_name.toLowerCase().includes(testTypeSearch.toLowerCase()) ||
      tt.test_category.toLowerCase().includes(testTypeSearch.toLowerCase())
  )

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Import Results</h1>
        <p className="text-muted-foreground text-sm">
          Add lab test results manually or import from PDF
        </p>
      </div>

      {/* Import Options */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="border-2 border-dashed cursor-not-allowed opacity-60">
          <CardContent className="flex flex-col items-center justify-center py-8">
            <Upload className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="font-medium">Upload PDF</p>
            <p className="text-xs text-muted-foreground mt-1">Coming soon</p>
          </CardContent>
        </Card>

        <Card
          className={`border-2 cursor-pointer transition-colors ${
            selectedLot ? "border-primary" : "border-dashed hover:border-primary/50"
          }`}
          onClick={() => !selectedLot && setIsLotDialogOpen(true)}
        >
          <CardContent className="flex flex-col items-center justify-center py-8">
            <ClipboardList className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="font-medium">Manual Entry</p>
            <p className="text-xs text-muted-foreground mt-1">
              {selectedLot ? `Lot: ${selectedLot.reference_number}` : "Enter results manually"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Manual Entry Form */}
      {selectedLot && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Selected Lot */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">Selected Lot</CardTitle>
                  <CardDescription>
                    {selectedLot.lot_number} ({selectedLot.reference_number})
                  </CardDescription>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSelectedLot(null)
                    setValue("lot_id", 0)
                    setValue("results", [])
                  }}
                >
                  Change Lot
                </Button>
              </div>
            </CardHeader>
          </Card>

          {/* Test Results */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Test Results
                  </CardTitle>
                  <CardDescription>
                    Add test results for this lot
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addBlankResult}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Add Blank
                  </Button>
                  <Button
                    type="button"
                    variant="default"
                    size="sm"
                    onClick={() => openTestTypeSelector()}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    From Catalog
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {fields.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No test results added yet</p>
                  <div className="flex gap-2 justify-center mt-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => openTestTypeSelector()}
                    >
                      Add from catalog
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {fields.map((field, index) => (
                    <div
                      key={field.id}
                      className="p-4 border rounded-lg space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 grid grid-cols-2 gap-3">
                          <div className="space-y-1">
                            <Label className="text-xs">Test Type *</Label>
                            <div className="flex gap-2">
                              <Input
                                {...register(`results.${index}.test_type`)}
                                placeholder="e.g., Total Plate Count"
                                className="flex-1"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => openTestTypeSelector(index)}
                              >
                                <Search className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>

                          <div className="space-y-1">
                            <Label className="text-xs">Result Value</Label>
                            <div className="flex gap-2">
                              <Input
                                {...register(`results.${index}.result_value`)}
                                placeholder="e.g., < 10"
                                className="flex-1"
                              />
                              <Input
                                {...register(`results.${index}.unit`)}
                                placeholder="Unit"
                                className="w-24"
                              />
                            </div>
                          </div>

                          <div className="space-y-1">
                            <Label className="text-xs">Specification</Label>
                            <Input
                              {...register(`results.${index}.specification`)}
                              placeholder="e.g., < 10,000 CFU/g"
                            />
                          </div>

                          <div className="space-y-1">
                            <Label className="text-xs">Method</Label>
                            <Input
                              {...register(`results.${index}.method`)}
                              placeholder="e.g., USP <2021>"
                            />
                          </div>
                        </div>

                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          className="ml-2"
                          onClick={() => remove(index)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {errors.results && (
                <p className="text-sm text-destructive mt-2">
                  {errors.results.message || errors.results.root?.message}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Submit */}
          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/")}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={bulkCreateMutation.isPending || fields.length === 0}
            >
              {bulkCreateMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Import {fields.length} Result{fields.length !== 1 ? "s" : ""}
            </Button>
          </div>
        </form>
      )}

      {/* Lot Selection Dialog */}
      <Dialog open={isLotDialogOpen} onOpenChange={setIsLotDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Select Lot</DialogTitle>
            <DialogDescription>
              Choose a lot to add test results to
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Input
              placeholder="Search lots..."
              value={lotSearch}
              onChange={(e) => setLotSearch(e.target.value)}
              autoFocus
            />

            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredLots?.map((lot) => (
                <button
                  key={lot.id}
                  type="button"
                  onClick={() => selectLot(lot)}
                  className="w-full text-left p-3 rounded hover:bg-muted"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium font-mono">{lot.reference_number}</p>
                      <p className="text-xs text-muted-foreground">{lot.lot_number}</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      lot.status === "PENDING"
                        ? "bg-yellow-100 text-yellow-800"
                        : lot.status === "APPROVED"
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-800"
                    }`}>
                      {lot.status.toLowerCase()}
                    </span>
                  </div>
                </button>
              ))}
              {filteredLots?.length === 0 && (
                <p className="text-center text-muted-foreground py-4">
                  No lots found
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsLotDialogOpen(false)}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Test Type Selection Dialog */}
      <Dialog open={isTestTypeDialogOpen} onOpenChange={setIsTestTypeDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Select Test Type</DialogTitle>
            <DialogDescription>
              Choose a test type from the catalog
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Input
              placeholder="Search test types..."
              value={testTypeSearch}
              onChange={(e) => setTestTypeSearch(e.target.value)}
              autoFocus
            />

            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredTestTypes?.map((tt) => (
                <button
                  key={tt.id}
                  type="button"
                  onClick={() => addTestType(tt)}
                  className="w-full text-left p-3 rounded hover:bg-muted"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{tt.test_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {tt.test_category}
                        {tt.default_unit && ` • ${tt.default_unit}`}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
              {filteredTestTypes?.length === 0 && (
                <p className="text-center text-muted-foreground py-4">
                  No test types found
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsTestTypeDialogOpen(false)
                setActiveResultIndex(null)
              }}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
