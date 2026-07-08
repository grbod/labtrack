import { useState, useMemo } from "react"
import { motion } from "framer-motion"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2, FlaskConical, ChevronDown, ChevronUp, CircleCheck, Ban, Save } from "lucide-react"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
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
import { ConfirmActionDialog } from "@/components/domain/ConfirmActionDialog"
import { ReasonDialog } from "@/components/domain/ReasonDialog"

import {
  useLabTestTypes,
  useLabTestTypeCategories,
  useCreateLabTestType,
  useUpdateLabTestType,
  useDeleteLabTestType,
} from "@/hooks/useLabTestTypes"
import {
  useApproveLabTestAlias,
  useDisableLabTestAlias,
  useLabTestBuiltinAliases,
  useLabTestAliases,
  useUpdateLabTestAlias,
} from "@/hooks/useLabTestAliases"
import type { LabTestAlias, LabTestType } from "@/types"
import type { CreateLabTestTypeData } from "@/api/labTestTypes"
import { useAuthStore } from "@/store/auth"

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
type SortField = "test_name" | "test_category"
type SortDirection = "asc" | "desc"
type AliasStatusFilter = "pending" | "approved" | "disabled" | "built_in"

export function LabTestTypesPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingType, setEditingType] = useState<LabTestType | null>(null)
  const [isBulkImportOpen, setIsBulkImportOpen] = useState(false)
  const [aliasStatus, setAliasStatus] = useState<AliasStatusFilter>("pending")
  const [editingAliasId, setEditingAliasId] = useState<number | null>(null)
  const [aliasDraft, setAliasDraft] = useState<{
    raw_phrase: string
    lab_name: string
    lab_test_type_id: number
  } | null>(null)
  const [pendingApproveAlias, setPendingApproveAlias] = useState<LabTestAlias | null>(null)
  const [pendingDisableAlias, setPendingDisableAlias] = useState<LabTestAlias | null>(null)

  // Sorting state
  const [sortField, setSortField] = useState<SortField | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc")

  const { data, isLoading } = useLabTestTypes({
    page,
    page_size: 50,
    search: search || undefined,
    category: categoryFilter || undefined,
  })
  const { data: activeTypes } = useLabTestTypes({ page_size: 500, is_active: true })
  const { user } = useAuthStore()
  // Alias review (approve/edit/disable) is QC/Admin only, matching the backend
  // endpoint guards; other roles don't see the section or fire the request.
  const canManageAliases = user?.role === "admin" || user?.role === "qc_manager"
  const { data: aliases, isLoading: aliasesLoading } = useLabTestAliases(
    {
      page_size: 25,
      status: aliasStatus === "built_in" ? "pending" : aliasStatus,
    },
    { enabled: canManageAliases && aliasStatus !== "built_in" }
  )
  const { data: builtinAliases, isLoading: builtinAliasesLoading } = useLabTestBuiltinAliases(
    { enabled: canManageAliases && aliasStatus === "built_in" }
  )
  const { data: categories } = useLabTestTypeCategories()
  const createMutation = useCreateLabTestType()
  const updateMutation = useUpdateLabTestType()
  const deleteMutation = useDeleteLabTestType()
  const updateAliasMutation = useUpdateLabTestAlias()
  const approveAliasMutation = useApproveLabTestAlias()
  const disableAliasMutation = useDisableLabTestAlias()

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

  // Sort handler
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // Toggle direction if same field
      setSortDirection(sortDirection === "asc" ? "desc" : "asc")
    } else {
      // Set new field with ascending direction
      setSortField(field)
      setSortDirection("asc")
    }
  }

  // Sorted items
  const sortedItems = useMemo(() => {
    if (!sortField || !data?.items) return data?.items
    return [...data.items].sort((a, b) => {
      const aVal = a[sortField] || ""
      const bVal = b[sortField] || ""
      const cmp = aVal.localeCompare(bVal)
      return sortDirection === "asc" ? cmp : -cmp
    })
  }, [data?.items, sortField, sortDirection])

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

  const startAliasEdit = (alias: LabTestAlias) => {
    setEditingAliasId(alias.id)
    setAliasDraft({
      raw_phrase: alias.raw_phrase,
      lab_name: alias.lab_name || "",
      lab_test_type_id: alias.lab_test_type_id,
    })
  }

  const saveAliasEdit = async () => {
    if (!editingAliasId || !aliasDraft) return
    await updateAliasMutation.mutateAsync({
      id: editingAliasId,
      data: {
        raw_phrase: aliasDraft.raw_phrase,
        lab_name: aliasDraft.lab_name.trim() || null,
        lab_test_type_id: aliasDraft.lab_test_type_id,
      },
    })
    setEditingAliasId(null)
    setAliasDraft(null)
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

  // Sortable header component
  const SortableHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <TableHead
      onClick={() => handleSort(field)}
      className="font-semibold text-slate-600 text-[13px] tracking-wide cursor-pointer hover:bg-slate-100/50 select-none"
    >
      <div className="flex items-center gap-1">
        {children}
        {sortField === field && (
          sortDirection === "asc" ? (
            <ChevronUp className="h-4 w-4 text-slate-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-500" />
          )
        )}
      </div>
    </TableHead>
  )

  return (
    <div className="mx-auto max-w-7xl p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.275 }}
        className="space-y-8"
      >
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
                <span className="font-semibold text-slate-700">Bulk Import Lab Test Types</span>
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
              <EmptyState
                icon={FlaskConical}
                title="No lab test types found"
                description="Get started by adding your first test type"
                actionLabel="Add your first test type"
                onAction={openCreateDialog}
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                    <SortableHeader field="test_name">Test Name</SortableHeader>
                    <SortableHeader field="test_category">Category</SortableHeader>
                    <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Method</TableHead>
                    <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Unit</TableHead>
                    <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Default Spec</TableHead>
                    <TableHead className="w-[100px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedItems?.map((testType) => (
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

          {canManageAliases && (
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-[18px] font-bold text-slate-900">Test aliases</h2>
                <p className="mt-0.5 text-[13px] text-slate-500">
                  Review importer alias suggestions before they affect future imports.
                </p>
              </div>
              <div className="flex gap-2">
                {(["pending", "approved", "disabled", "built_in"] as const).map((status) => (
                  <Button
                    key={status}
                    variant={aliasStatus === status ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setAliasStatus(status)
                      setEditingAliasId(null)
                      setAliasDraft(null)
                    }}
                    className={aliasStatus === status ? "bg-slate-900" : "border-slate-200"}
                  >
                    {status === "built_in" ? "built-in" : status}
                  </Button>
                ))}
              </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)]">
              {aliasStatus === "built_in" ? (
                builtinAliasesLoading ? (
                  <div className="flex items-center justify-center py-10">
                    <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
                  </div>
                ) : !builtinAliases?.items.length ? (
                  <div className="px-5 py-10 text-center text-sm text-slate-500">
                    No built-in aliases.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-slate-50/80 hover:bg-slate-50/80">
                        <TableHead>Raw phrase</TableHead>
                        <TableHead>Lab scope</TableHead>
                        <TableHead>Target test</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Source</TableHead>
                        <TableHead>Count</TableHead>
                        <TableHead>Last seen</TableHead>
                        <TableHead>Last file / lot</TableHead>
                        <TableHead className="w-[130px]">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {builtinAliases.items.map((alias) => (
                        <TableRow key={alias.raw_phrase}>
                          <TableCell>
                            <span className="font-medium text-slate-900">
                              {formatAliasPhrase(alias.raw_phrase)}
                            </span>
                          </TableCell>
                          <TableCell>Global</TableCell>
                          <TableCell>{alias.target_test_name}</TableCell>
                          <TableCell>Built-in</TableCell>
                          <TableCell>Normalization</TableCell>
                          <TableCell>-</TableCell>
                          <TableCell className="text-slate-500">Shipped</TableCell>
                          <TableCell className="text-slate-500">Importer Dictionary</TableCell>
                          <TableCell className="text-slate-500">Read-only</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )
              ) : aliasesLoading ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-300" />
                </div>
              ) : !aliases?.items.length ? (
                <div className="px-5 py-10 text-center text-sm text-slate-500">
                  No {aliasStatus} aliases.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/80 hover:bg-slate-50/80">
                      <TableHead>Raw phrase</TableHead>
                      <TableHead>Lab scope</TableHead>
                      <TableHead>Target test</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Count</TableHead>
                      <TableHead>Last seen</TableHead>
                      <TableHead>Last file / lot</TableHead>
                      <TableHead className="w-[130px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {aliases.items.map((alias) => {
                      const editing = editingAliasId === alias.id && aliasDraft
                      return (
                        <TableRow key={alias.id}>
                          <TableCell>
                            {editing ? (
                              <Input
                                value={aliasDraft.raw_phrase}
                                onChange={(event) =>
                                  setAliasDraft({ ...aliasDraft, raw_phrase: event.target.value })
                                }
                                className="h-8"
                              />
                            ) : (
                              <span className="font-medium text-slate-900">
                                {formatAliasPhrase(alias.raw_phrase)}
                              </span>
                            )}
                          </TableCell>
                          <TableCell>
                            {editing ? (
                              <Input
                                value={aliasDraft.lab_name}
                                onChange={(event) =>
                                  setAliasDraft({ ...aliasDraft, lab_name: event.target.value })
                                }
                                placeholder="Global"
                                className="h-8"
                              />
                            ) : (
                              alias.lab_name || "Global"
                            )}
                          </TableCell>
                          <TableCell>
                            {editing ? (
                              <select
                                value={aliasDraft.lab_test_type_id}
                                onChange={(event) =>
                                  setAliasDraft({
                                    ...aliasDraft,
                                    lab_test_type_id: Number(event.target.value),
                                  })
                                }
                                className="h-8 w-full rounded-md border border-slate-200 bg-white px-2 text-sm"
                              >
                                {(activeTypes?.items || []).map((type) => (
                                  <option key={type.id} value={type.id}>
                                    {type.test_name}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              alias.target_test_name || `#${alias.lab_test_type_id}`
                            )}
                          </TableCell>
                          <TableCell>{formatAliasLabel(alias.status)}</TableCell>
                          <TableCell>{formatAliasLabel(alias.source)}</TableCell>
                          <TableCell>{alias.suggestion_count}</TableCell>
                          <TableCell className="text-slate-500">
                            {alias.last_seen_at ? new Date(alias.last_seen_at).toLocaleDateString() : "-"}
                          </TableCell>
                          <TableCell className="max-w-[180px] truncate text-slate-500">
                            {alias.last_filename || "-"}
                            {alias.last_lot_id ? ` · lot #${alias.last_lot_id}` : ""}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              {editing ? (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={saveAliasEdit}
                                  disabled={updateAliasMutation.isPending}
                                  className="h-8 w-8 p-0"
                                >
                                  <Save className="h-4 w-4" />
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => startAliasEdit(alias)}
                                  className="h-8 w-8 p-0"
                                >
                                  <Pencil className="h-4 w-4" />
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setPendingApproveAlias(alias)}
                                disabled={alias.status === "approved" || approveAliasMutation.isPending}
                                className="h-8 w-8 p-0 text-emerald-600"
                              >
                                <CircleCheck className="h-4 w-4" />
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setPendingDisableAlias(alias)}
                                disabled={alias.status === "disabled" || disableAliasMutation.isPending}
                                className="h-8 w-8 p-0 text-red-600"
                              >
                                <Ban className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          </section>
          )}

      {/* Approve alias confirmation */}
      <ConfirmActionDialog
        open={pendingApproveAlias !== null}
        onOpenChange={(open) => {
          if (!open) setPendingApproveAlias(null)
        }}
        title="Approve this alias?"
        description={
          pendingApproveAlias
            ? `Approving remaps "${formatAliasPhrase(pendingApproveAlias.raw_phrase)}" to ${
                pendingApproveAlias.target_test_name || `test #${pendingApproveAlias.lab_test_type_id}`
              } for ALL future imports.`
            : ""
        }
        confirmLabel="Approve alias"
        destructive={false}
        onConfirm={() => {
          if (pendingApproveAlias) approveAliasMutation.mutate(pendingApproveAlias.id)
        }}
      />

      {/* Disable alias with optional reason */}
      <ReasonDialog
        open={pendingDisableAlias !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDisableAlias(null)
        }}
        title="Disable this alias?"
        description={
          pendingDisableAlias
            ? `"${formatAliasPhrase(pendingDisableAlias.raw_phrase)}" will no longer map to ${
                pendingDisableAlias.target_test_name ||
                `test #${pendingDisableAlias.lab_test_type_id}`
              } on future imports.`
            : undefined
        }
        placeholder="Why is this alias being disabled?"
        confirmLabel="Disable alias"
        onConfirm={(reason) => {
          if (pendingDisableAlias) {
            disableAliasMutation.mutate({
              id: pendingDisableAlias.id,
              reason: reason || undefined,
            })
          }
        }}
      />

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
      </motion.div>
    </div>
  )
}

function formatAliasLabel(value: string) {
  return value
    .split("_")
    .map((part) => (part ? part.charAt(0).toUpperCase() + part.slice(1) : part))
    .join(" ")
}

function formatAliasPhrase(value: string) {
  return value
    .split(" ")
    .map(formatAliasPhraseToken)
    .join(" ")
}

function formatAliasPhraseToken(token: string): string {
  if (token.includes("/")) {
    return token.split("/").map(formatAliasPhraseToken).join("/")
  }
  if (token === "&") return token

  const normalized = token.toLowerCase()
  const specialCases: Record<string, string> = {
    "e.": "E.",
    e: "E",
    coli: "coli",
    spp: "spp.",
    pb: "Pb",
    as: "As",
    cd: "Cd",
    hg: "Hg",
    and: "and",
  }

  return (
    specialCases[normalized] ||
    normalized.charAt(0).toUpperCase() + normalized.slice(1)
  )
}
