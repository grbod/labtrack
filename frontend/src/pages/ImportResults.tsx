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
  ArrowRight,
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

  const { register, handleSubmit, control, setValue, formState: { errors } } = form
  const { fields, append, remove } = useFieldArray({
    control,
    name: "results",
  })

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
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Import Results</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Add lab test results manually or import from PDF
        </p>
      </div>

      {/* Import Options */}
      <div className="grid grid-cols-2 gap-5">
        <div className="rounded-xl border-2 border-dashed border-slate-200/80 bg-white p-8 flex flex-col items-center justify-center opacity-50 cursor-not-allowed shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
          <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
            <Upload className="h-7 w-7 text-slate-400" />
          </div>
          <p className="font-semibold text-slate-700 text-[15px]">Upload PDF</p>
          <p className="text-[13px] text-slate-400 mt-1">Coming soon</p>
        </div>

        <div
          className={`rounded-xl border-2 bg-white p-8 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] ${
            selectedLot
              ? "border-slate-900 shadow-[0_4px_12px_0_rgba(0,0,0,0.08)]"
              : "border-dashed border-slate-200/80 hover:border-slate-400 hover:shadow-[0_4px_12px_0_rgba(0,0,0,0.05)]"
          }`}
          onClick={() => !selectedLot && setIsLotDialogOpen(true)}
        >
          <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 transition-colors ${
            selectedLot ? "bg-slate-900" : "bg-slate-100"
          }`}>
            <ClipboardList className={`h-7 w-7 ${selectedLot ? "text-white" : "text-slate-500"}`} />
          </div>
          <p className="font-semibold text-slate-700 text-[15px]">Manual Entry</p>
          <p className="text-[13px] text-slate-500 mt-1">
            {selectedLot ? `Lot: ${selectedLot.reference_number}` : "Enter results manually"}
          </p>
        </div>
      </div>

      {/* Manual Entry Form */}
      {selectedLot && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Selected Lot */}
          <div className="rounded-xl border border-slate-200/60 bg-white px-6 py-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-slate-900 text-[15px]">Selected Lot</p>
                <p className="text-[14px] text-slate-500 mt-0.5">
                  {selectedLot.lot_number} ({selectedLot.reference_number})
                </p>
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
                className="border-slate-200 h-9"
              >
                Change Lot
              </Button>
            </div>
          </div>

          {/* Test Results */}
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
            <div className="border-b border-slate-100 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-slate-600" />
                    <h2 className="font-semibold text-slate-900 text-[15px]">Test Results</h2>
                  </div>
                  <p className="mt-1 text-[13px] text-slate-500">Add test results for this lot</p>
                </div>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={addBlankResult} className="border-slate-200 h-9">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Blank
                  </Button>
                  <Button type="button" size="sm" onClick={() => openTestTypeSelector()} className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-9">
                    <Plus className="mr-2 h-4 w-4" />
                    From Catalog
                  </Button>
                </div>
              </div>
            </div>
            <div className="p-6">
              {fields.length === 0 ? (
                <div className="text-center py-10">
                  <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center">
                    <FileText className="h-7 w-7 text-slate-400" />
                  </div>
                  <p className="mt-4 text-[14px] font-medium text-slate-600">No test results added yet</p>
                  <p className="mt-1 text-[13px] text-slate-500">Add results from the catalog or create blank entries</p>
                  <button
                    type="button"
                    onClick={() => openTestTypeSelector()}
                    className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                  >
                    Add from catalog
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {fields.map((field, index) => (
                    <div key={field.id} className="p-4 border border-slate-200/80 rounded-xl bg-slate-50/30 space-y-3 hover:bg-slate-50/50 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 grid grid-cols-2 gap-3">
                          <div className="space-y-1.5">
                            <Label className="text-[12px] font-semibold text-slate-600">Test Type *</Label>
                            <div className="flex gap-2">
                              <Input
                                {...register(`results.${index}.test_type`)}
                                placeholder="e.g., Total Plate Count"
                                className="flex-1 border-slate-200 h-10 bg-white"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => openTestTypeSelector(index)}
                                className="h-10 w-10 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg"
                              >
                                <Search className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>

                          <div className="space-y-1.5">
                            <Label className="text-[12px] font-semibold text-slate-600">Result Value</Label>
                            <div className="flex gap-2">
                              <Input
                                {...register(`results.${index}.result_value`)}
                                placeholder="e.g., < 10"
                                className="flex-1 border-slate-200 h-10 bg-white"
                              />
                              <Input
                                {...register(`results.${index}.unit`)}
                                placeholder="Unit"
                                className="w-24 border-slate-200 h-10 bg-white"
                              />
                            </div>
                          </div>

                          <div className="space-y-1.5">
                            <Label className="text-[12px] font-semibold text-slate-600">Specification</Label>
                            <Input
                              {...register(`results.${index}.specification`)}
                              placeholder="e.g., < 10,000 CFU/g"
                              className="border-slate-200 h-10 bg-white"
                            />
                          </div>

                          <div className="space-y-1.5">
                            <Label className="text-[12px] font-semibold text-slate-600">Method</Label>
                            <Input
                              {...register(`results.${index}.method`)}
                              placeholder="e.g., USP <2021>"
                              className="border-slate-200 h-10 bg-white"
                            />
                          </div>
                        </div>

                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="ml-3 h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          onClick={() => remove(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {errors.results && (
                <p className="text-[13px] text-red-600 mt-3">
                  {errors.results.message || errors.results.root?.message}
                </p>
              )}
            </div>
          </div>

          {/* Submit */}
          <div className="flex gap-3">
            <Button type="button" variant="outline" onClick={() => navigate("/")} className="border-slate-200 h-10">
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={bulkCreateMutation.isPending || fields.length === 0}
              className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
            >
              {bulkCreateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Import {fields.length} Result{fields.length !== 1 ? "s" : ""}
            </Button>
          </div>
        </form>
      )}

      {/* Lot Selection Dialog */}
      <Dialog open={isLotDialogOpen} onOpenChange={setIsLotDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">Select Lot</DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">Choose a lot to add test results to</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Input
              placeholder="Search lots..."
              value={lotSearch}
              onChange={(e) => setLotSearch(e.target.value)}
              autoFocus
              className="border-slate-200 h-11"
            />
            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredLots?.map((lot) => (
                <button
                  key={lot.id}
                  type="button"
                  onClick={() => selectLot(lot)}
                  className="w-full text-left p-3.5 rounded-xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-200"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold font-mono text-slate-900 text-[14px] tracking-wide">{lot.reference_number}</p>
                      <p className="text-[12px] text-slate-500 mt-0.5">{lot.lot_number}</p>
                    </div>
                    <span className={`text-[11px] px-2.5 py-1 rounded-full font-semibold tracking-wide ${
                      lot.status === "pending"
                        ? "bg-amber-100 text-amber-700"
                        : lot.status === "approved"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-600"
                    }`}>
                      {lot.status.charAt(0) + lot.status.slice(1).toLowerCase()}
                    </span>
                  </div>
                </button>
              ))}
              {filteredLots?.length === 0 && (
                <p className="text-center text-[14px] text-slate-500 py-6">No lots found</p>
              )}
            </div>
          </div>
          <DialogFooter className="pt-4">
            <Button type="button" variant="outline" onClick={() => setIsLotDialogOpen(false)} className="border-slate-200 h-10">
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Test Type Selection Dialog */}
      <Dialog open={isTestTypeDialogOpen} onOpenChange={setIsTestTypeDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">Select Test Type</DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">Choose a test type from the catalog</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Input
              placeholder="Search test types..."
              value={testTypeSearch}
              onChange={(e) => setTestTypeSearch(e.target.value)}
              autoFocus
              className="border-slate-200 h-11"
            />
            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredTestTypes?.map((tt) => (
                <button
                  key={tt.id}
                  type="button"
                  onClick={() => addTestType(tt)}
                  className="w-full text-left p-3.5 rounded-xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-200"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-900 text-[14px]">{tt.test_name}</p>
                      <p className="text-[12px] text-slate-500 mt-0.5">
                        {tt.test_category}
                        {tt.default_unit && ` - ${tt.default_unit}`}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
              {filteredTestTypes?.length === 0 && (
                <p className="text-center text-[14px] text-slate-500 py-6">No test types found</p>
              )}
            </div>
          </div>
          <DialogFooter className="pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsTestTypeDialogOpen(false)
                setActiveResultIndex(null)
              }}
              className="border-slate-200 h-10"
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
