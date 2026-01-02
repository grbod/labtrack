import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2, FlaskConical } from "lucide-react"

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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import {
  useLabTestTypes,
  useLabTestTypeCategories,
  useCreateLabTestType,
  useUpdateLabTestType,
  useDeleteLabTestType,
} from "@/hooks/useLabTestTypes"
import type { LabTestType } from "@/types"
import type { CreateLabTestTypeData } from "@/api/labTestTypes"

// Common lab test categories
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
  abbreviations: z.string().optional(),
  default_specification: z.string().optional(),
})

type LabTestTypeForm = z.infer<typeof labTestTypeSchema>

export function LabTestTypesPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingType, setEditingType] = useState<LabTestType | null>(null)

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

  const { register, handleSubmit, reset, formState: { errors }, setValue, watch } = form
  const watchedCategory = watch("test_category")

  const openCreateDialog = () => {
    setEditingType(null)
    reset({
      test_name: "",
      test_category: "",
      default_unit: "",
      description: "",
      test_method: "",
      abbreviations: "",
      default_specification: "",
    })
    setIsDialogOpen(true)
  }

  const openEditDialog = (testType: LabTestType) => {
    setEditingType(testType)
    reset({
      test_name: testType.test_name,
      test_category: testType.test_category,
      default_unit: testType.default_unit || "",
      description: testType.description || "",
      test_method: testType.test_method || "",
      abbreviations: testType.abbreviations || "",
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
      abbreviations: formData.abbreviations || undefined,
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

  // Get category badge color based on category
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      "Microbiological": "bg-green-100 text-green-800",
      "Heavy Metals": "bg-red-100 text-red-800",
      "Pesticides": "bg-orange-100 text-orange-800",
      "Nutritional": "bg-blue-100 text-blue-800",
      "Physical": "bg-purple-100 text-purple-800",
      "Chemical": "bg-yellow-100 text-yellow-800",
      "Allergens": "bg-pink-100 text-pink-800",
      "Organoleptic": "bg-teal-100 text-teal-800",
    }
    return colors[category] || "bg-gray-100 text-gray-800"
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Lab Test Types</h1>
          <p className="text-muted-foreground text-sm">Manage the catalog of available lab tests</p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Add Test Type
        </Button>
      </div>

      {/* Category Summary */}
      {categories && categories.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          <Button
            variant={categoryFilter === "" ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setCategoryFilter("")
              setPage(1)
            }}
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
            >
              {cat.category} ({cat.count})
            </Button>
          ))}
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search test types..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
                className="pl-8"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FlaskConical className="h-4 w-4" />
            {data?.total ?? 0} Test Types
          </CardTitle>
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
                  <TableHead>Test Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead>Default Spec</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((testType) => (
                  <TableRow key={testType.id}>
                    <TableCell className="font-medium">
                      <div>
                        {testType.test_name}
                        {testType.abbreviations && (
                          <span className="text-xs text-muted-foreground ml-2">
                            ({testType.abbreviations})
                          </span>
                        )}
                      </div>
                      {testType.description && (
                        <p className="text-xs text-muted-foreground truncate max-w-xs">
                          {testType.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${getCategoryColor(testType.test_category)}`}>
                        {testType.test_category}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {testType.test_method || "-"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {testType.default_unit || "-"}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {testType.default_specification || "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => openEditDialog(testType)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => handleDelete(testType.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {data?.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                      No lab test types found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}
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
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={page === data.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingType ? "Edit Lab Test Type" : "Add Lab Test Type"}
            </DialogTitle>
            <DialogDescription>
              {editingType
                ? "Update lab test type information"
                : "Add a new lab test type to the catalog"}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="test_name">Test Name *</Label>
                <Input
                  id="test_name"
                  {...register("test_name")}
                  placeholder="e.g., Total Plate Count"
                  aria-invalid={!!errors.test_name}
                />
                {errors.test_name && (
                  <p className="text-sm text-destructive">{errors.test_name.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="test_category">Category *</Label>
                <div className="relative">
                  <Input
                    id="test_category"
                    {...register("test_category")}
                    placeholder="Select or type..."
                    list="categories-list"
                    aria-invalid={!!errors.test_category}
                  />
                  <datalist id="categories-list">
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat} />
                    ))}
                  </datalist>
                </div>
                {errors.test_category && (
                  <p className="text-sm text-destructive">{errors.test_category.message}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="test_method">Test Method</Label>
                <Input
                  id="test_method"
                  {...register("test_method")}
                  placeholder="e.g., USP <2021>"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="default_unit">Default Unit</Label>
                <Input
                  id="default_unit"
                  {...register("default_unit")}
                  placeholder="e.g., CFU/g, ppm"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="default_specification">Default Specification</Label>
              <Input
                id="default_specification"
                {...register("default_specification")}
                placeholder="e.g., < 10,000 CFU/g"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="abbreviations">Abbreviations / Aliases</Label>
              <Input
                id="abbreviations"
                {...register("abbreviations")}
                placeholder="e.g., TPC, APC"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                {...register("description")}
                placeholder="Brief description of what this test measures"
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isMutating}>
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
