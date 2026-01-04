import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2, FlaskConical, ArrowRight, ChevronDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { LabTestTypeBulkImport } from "@/components/bulk-import/LabTestTypeBulkImport"

import {
  useLabTestTypes,
  useLabTestTypeCategories,
  useCreateLabTestType,
  useUpdateLabTestType,
  useDeleteLabTestType,
} from "@/hooks/useLabTestTypes"
import type { LabTestType } from "@/types"
import type { CreateLabTestTypeData } from "@/api/labTestTypes"

const CATEGORIES = [
  "Microbiological",
  "Heavy Metals",
  "Pesticides",
  "Nutritional",
  "Physical",
  "Chemical",
  "Allergens",
  "Organoleptic",
]

const labTestTypeSchema = z.object({
  test_name: z.string().min(1, "Test name is required"),
  test_category: z.string().min(1, "Category is required"),
  default_unit: z.string().optional(),
  description: z.string().optional(),
  test_method: z.string().optional(),
  default_specification: z.string().optional(),
})

type LabTestTypeForm = z.infer<typeof labTestTypeSchema>

export function LabTestTypesPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingType, setEditingType] = useState<LabTestType | null>(null)
  const [isBulkImportOpen, setIsBulkImportOpen] = useState(false)

  const { data, isLoading } = useLabTestTypes({
    page,
    page_size: 50,
    search: search || undefined,
    category: categoryFilter || undefined,
  })
  const { data: categories } = useLabTestTypeCategories()
  const createMutation = useCreateLabTestType()
  const updateMutation = useUpdateLabTestType()
  const deleteMutation = useDeleteLabTestType()

  const form = useForm<LabTestTypeForm>({
    resolver: zodResolver(labTestTypeSchema),
    defaultValues: {},
  })

  const { register, handleSubmit, reset, formState: { errors }, watch, setValue } = form
  const [isAddingCategory, setIsAddingCategory] = useState(false)

  // Watch form values for display name computation
  const watchedTestName = watch("test_name")
  const watchedSpec = watch("default_specification")
  const watchedUnit = watch("default_unit")

  const computeDisplayName = () => {
    let result = watchedTestName || ''
    if (watchedSpec) result += ` (${watchedSpec} [default])`
    if (watchedUnit) result += ` ${watchedUnit}`
    return result || '-'
  }

  const openCreateDialog = () => {
    setEditingType(null)
    setIsAddingCategory(false)
    reset({
      test_name: "",
      test_category: "",
      default_unit: "",
      description: "",
      test_method: "",
      default_specification: "",
    })
    setIsDialogOpen(true)
  }

  const openEditDialog = (testType: LabTestType) => {
    setEditingType(testType)
    setIsAddingCategory(false)
    reset({
      test_name: testType.test_name,
      test_category: testType.test_category,
      default_unit: testType.default_unit || "",
      description: testType.description || "",
      test_method: testType.test_method || "",
      default_specification: testType.default_specification || "",
    })
    setIsDialogOpen(true)
  }

  const onSubmit = async (formData: LabTestTypeForm) => {
    const data: CreateLabTestTypeData = {
      test_name: formData.test_name,
      test_category: formData.test_category,
      default_unit: formData.default_unit || undefined,
      description: formData.description || undefined,
      test_method: formData.test_method || undefined,
      default_specification: formData.default_specification || undefined,
    }

    try {
      if (editingType) {
        await updateMutation.mutateAsync({ id: editingType.id, data })
      } else {
        await createMutation.mutateAsync(data)
      }
      setIsDialogOpen(false)
    } catch {
      // Error handled by mutation
    }
  }

  const handleDelete = async (id: number) => {
    if (confirm("Are you sure you want to delete this lab test type?")) {
      try {
        await deleteMutation.mutateAsync(id)
      } catch {
        // Error might indicate test type is in use
      }
    }
  }

  const isMutating = createMutation.isPending || updateMutation.isPending

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      "Microbiological": "bg-emerald-100 text-emerald-700",
      "Heavy Metals": "bg-red-100 text-red-700",
      "Pesticides": "bg-orange-100 text-orange-700",
      "Nutritional": "bg-blue-100 text-blue-700",
      "Physical": "bg-violet-100 text-violet-700",
      "Chemical": "bg-amber-100 text-amber-700",
      "Allergens": "bg-pink-100 text-pink-700",
      "Organoleptic": "bg-teal-100 text-teal-700",
    }
    return colors[category] || "bg-slate-100 text-slate-600"
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Lab Test Types</h1>
          <p className="mt-1.5 text-[15px] text-slate-500">Manage the catalog of available lab tests</p>
        </div>
        <Button
          onClick={openCreateDialog}
          className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10 px-4"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Test Type
        </Button>
      </div>

      {/* Category Filter */}
      {categories && categories.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          <Button
            variant={categoryFilter === "" ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setCategoryFilter("")
              setPage(1)
            }}
            className={categoryFilter === "" ? "bg-slate-900 hover:bg-slate-800 shadow-sm h-9" : "border-slate-200 h-9"}
          >
            All
          </Button>
          {categories.map((cat) => (
            <Button
              key={cat.category}
              variant={categoryFilter === cat.category ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setCategoryFilter(cat.category)
                setPage(1)
              }}
              className={categoryFilter === cat.category ? "bg-slate-900 hover:bg-slate-800 shadow-sm h-9" : "border-slate-200 h-9"}
            >
              {cat.category} ({cat.count})
            </Button>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search test types..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            className="pl-10 h-11 bg-white border-slate-200 rounded-lg shadow-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 transition-shadow"
          />
        </div>
        <span className="text-[14px] font-medium text-slate-500">{data?.total ?? 0} test types</span>
      </div>

      {/* Bulk Import */}
      <Collapsible open={isBulkImportOpen} onOpenChange={setIsBulkImportOpen}>
        <CollapsibleTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between h-11 bg-white hover:bg-slate-50"
          >
            <span className="font-semibold text-slate-700">📊 Bulk Import Lab Test Types</span>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${
                isBulkImportOpen ? "rotate-180" : ""
              }`}
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4">
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-sm p-6">
            <LabTestTypeBulkImport />
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : data?.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center">
              <FlaskConical className="h-8 w-8 text-slate-400" />
            </div>
            <p className="mt-5 text-[15px] font-medium text-slate-600">No lab test types found</p>
            <p className="mt-1 text-[14px] text-slate-500">Get started by adding your first test type</p>
            <button
              onClick={openCreateDialog}
              className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold text-blue-600 hover:text-blue-700 transition-colors"
            >
              Add your first test type
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Test Name</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Category</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Method</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Unit</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Default Spec</TableHead>
                <TableHead className="w-[100px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((testType) => (
                <TableRow key={testType.id} className="hover:bg-slate-50/50 transition-colors">
                  <TableCell>
                    <div>
                      <span className="font-semibold text-slate-900 text-[14px]">{testType.test_name}</span>
                    </div>
                    {testType.description && (
                      <p className="text-[12px] text-slate-500 truncate max-w-xs mt-0.5">{testType.description}</p>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${getCategoryColor(testType.test_category)}`}>
                      {testType.test_category}
                    </span>
                  </TableCell>
                  <TableCell className="text-slate-500 text-[14px]">{testType.test_method || "-"}</TableCell>
                  <TableCell className="text-slate-500 text-[14px]">{testType.default_unit || "-"}</TableCell>
                  <TableCell className="text-slate-500 text-[13px]">{testType.default_specification || "-"}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-0.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditDialog(testType)}
                        className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(testType.id)}
                        disabled={deleteMutation.isPending}
                        className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 px-5 py-4">
            <p className="text-[14px] text-slate-500">
              Page {data.page} of {data.total_pages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="border-slate-200 hover:bg-slate-50 h-9"
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="border-slate-200 hover:bg-slate-50 h-9"
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">
              {editingType ? "Edit Lab Test Type" : "Add Lab Test Type"}
            </DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              {editingType ? "Update lab test type information" : "Add a new lab test type to the catalog"}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="test_name" className="text-[13px] font-semibold text-slate-700">Test Name *</Label>
                <Input id="test_name" {...register("test_name")} placeholder="e.g., Total Plate Count" aria-invalid={!!errors.test_name} className="border-slate-200 h-10" />
                {errors.test_name && <p className="text-[13px] text-red-600">{errors.test_name.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="test_category" className="text-[13px] font-semibold text-slate-700">Category *</Label>
                {isAddingCategory ? (
                  <Input
                    id="test_category"
                    {...register("test_category")}
                    placeholder="Enter new category name..."
                    autoFocus
                    className="border-slate-200 h-10"
                    onBlur={(e) => {
                      if (!e.target.value) {
                        setIsAddingCategory(false)
                      }
                    }}
                  />
                ) : (
                  <select
                    id="test_category"
                    value={watch("test_category") || ""}
                    onChange={(e) => {
                      if (e.target.value === "__add_new__") {
                        setValue("test_category", "")
                        setIsAddingCategory(true)
                      } else {
                        setValue("test_category", e.target.value)
                      }
                    }}
                    className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2"
                  >
                    <option value="">Select category...</option>
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                    {/* Show current value if it's a custom category not in presets */}
                    {watch("test_category") && !CATEGORIES.includes(watch("test_category")) && (
                      <option value={watch("test_category")}>{watch("test_category")} (custom)</option>
                    )}
                    <option value="__add_new__">+ Add new category...</option>
                  </select>
                )}
                {errors.test_category && <p className="text-[13px] text-red-600">{errors.test_category.message}</p>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="test_method" className="text-[13px] font-semibold text-slate-700">Test Method</Label>
                <Input id="test_method" {...register("test_method")} placeholder="e.g., USP <2021>" className="border-slate-200 h-10" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="default_unit" className="text-[13px] font-semibold text-slate-700">Default Unit</Label>
                <Input id="default_unit" {...register("default_unit")} placeholder="e.g., CFU/g, ppm" className="border-slate-200 h-10" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="default_specification" className="text-[13px] font-semibold text-slate-700">Default Specification</Label>
              <Input id="default_specification" {...register("default_specification")} placeholder="e.g., < 10,000 CFU/g" className="border-slate-200 h-10" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[13px] font-semibold text-slate-700">Display Name</Label>
              <div className="flex h-10 w-full items-center rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                {computeDisplayName()}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="description" className="text-[13px] font-semibold text-slate-700">Description <span className="font-normal text-slate-400">(optional)</span></Label>
              <Input id="description" {...register("description")} placeholder="Brief description" className="border-slate-200 h-10" />
            </div>
            <DialogFooter className="pt-4">
              <Button type="button" variant="outline" onClick={() => setIsDialogOpen(false)} className="border-slate-200 h-10">
                Cancel
              </Button>
              <Button type="submit" disabled={isMutating} className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10">
                {isMutating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingType ? "Save Changes" : "Add Test Type"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
