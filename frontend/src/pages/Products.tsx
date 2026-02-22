import { useState, useRef, useMemo, useCallback, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { Plus, Pencil, Archive, Search, Loader2, Package, Check, X, Trash2 } from "lucide-react"
import { useReactTable, getCoreRowModel, createColumnHelper, flexRender } from "@tanstack/react-table"
import { TestSpecsTooltip } from "@/components/domain/TestSpecsTooltip"
import { LabTestTypeAutocomplete } from "@/components/form/LabTestTypeAutocomplete"
import { generateDisplayName } from "@/lib/product-utils"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

import {
  useProducts,
  useCreateProduct,
  useUpdateProduct,
  useArchiveProduct,
  useCreateSize,
  useUpdateSize,
  useDeleteSize,
  useProductTestSpecs,
  useCreateTestSpec,
  useUpdateTestSpec,
  useDeleteTestSpec,
} from "@/hooks/useProducts"
import { productsApi } from "@/api/products"
import { useAuthStore } from "@/store/auth"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import type { Product, ProductSize, ProductTestSpecification, LabTestType } from "@/types"

// SizeChips component for inline size management
interface SizeChipsProps {
  sizes: ProductSize[]
  productId: number
  onAddSize: (productId: number, size: string) => void
  onEditSize: (productId: number, sizeId: number, newSize: string) => void
  onDeleteSize: (productId: number, sizeId: number) => void
}

function SizeChips({ sizes, productId, onAddSize, onEditSize, onDeleteSize }: SizeChipsProps) {
  const [isAdding, setIsAdding] = useState(false)
  const [newSize, setNewSize] = useState("")
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editValue, setEditValue] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isAdding && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isAdding])

  const handleAddSubmit = () => {
    if (newSize.trim()) {
      onAddSize(productId, newSize.trim())
      setNewSize("")
      setIsAdding(false)
    }
  }

  const handleEditSubmit = (sizeId: number) => {
    if (editValue.trim()) {
      onEditSize(productId, sizeId, editValue.trim())
      setEditingId(null)
      setEditValue("")
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
    if (e.key === "Enter") {
      e.preventDefault()
      action()
    } else if (e.key === "Escape") {
      setIsAdding(false)
      setEditingId(null)
      setNewSize("")
      setEditValue("")
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {sizes.map((size) => (
        <Popover key={size.id} open={editingId === size.id} onOpenChange={(open) => {
          if (open) {
            setEditingId(size.id)
            setEditValue(size.size)
          } else {
            setEditingId(null)
            setEditValue("")
          }
        }}>
          <PopoverTrigger asChild>
            <button
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[12px] font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors group"
            >
              {size.size}
              <X className="h-3 w-3 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-48 p-2" align="start">
            <div className="space-y-2">
              <Input
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => handleKeyDown(e, () => handleEditSubmit(size.id))}
                placeholder="Edit size..."
                className="h-8 text-sm"
                autoFocus
              />
              <div className="flex gap-1">
                <Button
                  size="sm"
                  onClick={() => handleEditSubmit(size.id)}
                  disabled={!editValue.trim()}
                  className="flex-1 h-7 text-xs bg-slate-900 hover:bg-slate-800"
                >
                  Save
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    onDeleteSize(productId, size.id)
                    setEditingId(null)
                  }}
                  className="h-7 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>
      ))}

      {isAdding ? (
        <div className="inline-flex items-center gap-1">
          <Input
            ref={inputRef}
            value={newSize}
            onChange={(e) => setNewSize(e.target.value)}
            onKeyDown={(e) => handleKeyDown(e, handleAddSubmit)}
            onBlur={() => {
              if (!newSize.trim()) setIsAdding(false)
            }}
            placeholder="e.g., 2lb"
            className="h-6 w-16 text-[12px] px-1.5"
          />
          <button
            onClick={handleAddSubmit}
            disabled={!newSize.trim()}
            className="p-0.5 rounded hover:bg-slate-100 text-slate-500 hover:text-emerald-600 disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => {
              setIsAdding(false)
              setNewSize("")
            }}
            className="p-0.5 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-700"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <button
          onClick={() => setIsAdding(true)}
          className="inline-flex items-center justify-center w-5 h-5 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          title="Add size"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      )}

      {sizes.length === 0 && !isAdding && (
        <span className="text-[12px] text-slate-400">No sizes</span>
      )}
    </div>
  )
}

// Type for test spec table rows (existing specs + add row)
interface TestSpecRow {
  id: number | 'new'
  lab_test_type_id: number | null
  test_name: string
  test_method: string | null
  test_category: string | null
  test_unit: string | null
  specification: string
  is_required: boolean
  isAddRow?: boolean
}

// Inline editing values type
interface InlineEditValues {
  brand: string
  product_name: string
  flavor: string
  serving_size: string
  expiry_duration_months: number
  version: string
}

export function ProductsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")

  // Inline editing state
  const [editingProductId, setEditingProductId] = useState<number | null>(null)
  const [editValues, setEditValues] = useState<InlineEditValues | null>(null)
  const [editErrors, setEditErrors] = useState<Record<string, string>>({})
  const [isSavingEdit, setIsSavingEdit] = useState(false)

  // Inline add row state
  const [showAddRow, setShowAddRow] = useState(false)
  const [addRowValues, setAddRowValues] = useState<InlineEditValues>({
    brand: "",
    product_name: "",
    flavor: "",
    serving_size: "",
    expiry_duration_months: 36,
    version: "",
  })
  const [addRowErrors, setAddRowErrors] = useState<Record<string, string>>({})
  const [isSavingAdd, setIsSavingAdd] = useState(false)

  // Refs for focus management
  const editRowRef = useRef<HTMLTableRowElement>(null)
  const addRowRef = useRef<HTMLTableRowElement>(null)
  const addRowBrandInputRef = useRef<HTMLInputElement>(null)

  // Test specs dialog state
  const [isTestSpecsDialogOpen, setIsTestSpecsDialogOpen] = useState(false)
  const [selectedProductForSpecs, setSelectedProductForSpecs] = useState<Product | null>(null)

  // Inline add row state for test specs
  const [addRowTestType, setAddRowTestType] = useState<LabTestType | null>(null)
  const [addRowSpecification, setAddRowSpecification] = useState("")
  const [addRowRequired, setAddRowRequired] = useState(true)
  const [editingSpecCell, setEditingSpecCell] = useState<{ rowId: number; columnId: string } | null>(null)

  // Refs for add row tab navigation
  const addRowSpecInputRef = useRef<HTMLInputElement>(null)
  const addRowRequiredRef = useRef<HTMLInputElement>(null)
  const addRowTestTypeRef = useRef<{ focus: () => void } | null>(null)

  const { user } = useAuthStore()
  const isAdmin = user?.role === "admin" || user?.role === "qc_manager"

  const { data, isLoading } = useProducts({ page, page_size: 50, search: search || undefined })
  const createMutation = useCreateProduct()
  const updateMutation = useUpdateProduct()
  const archiveMutation = useArchiveProduct()

  // Archive dialog state
  const [archiveDialogProduct, setArchiveDialogProduct] = useState<Product | null>(null)
  const [archiveReason, setArchiveReason] = useState("")

  // Size mutation hooks
  const createSizeMutation = useCreateSize()
  const updateSizeMutation = useUpdateSize()
  const deleteSizeMutation = useDeleteSize()

  // Test specs hooks
  const { data: testSpecs } = useProductTestSpecs(selectedProductForSpecs?.id ?? 0)
  const { data: labTestTypes } = useLabTestTypes({ page_size: 500 })
  const createTestSpecMutation = useCreateTestSpec()
  const updateTestSpecMutation = useUpdateTestSpec()
  const deleteTestSpecMutation = useDeleteTestSpec()

  // Handle ?addNew=true URL param (from Create Sample page)
  useEffect(() => {
    if (searchParams.get('addNew') === 'true' && !isLoading) {
      // Show the add row
      setShowAddRow(true)
      // Clear the URL param
      setSearchParams({}, { replace: true })
      // Scroll to bottom and focus Brand input after render
      setTimeout(() => {
        addRowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        addRowBrandInputRef.current?.focus()
      }, 150)
    }
  }, [searchParams, setSearchParams, isLoading])

  // Inline editing handlers
  const startEditing = (product: Product) => {
    setEditingProductId(product.id)
    setEditValues({
      brand: product.brand,
      product_name: product.product_name,
      flavor: product.flavor || "",
      serving_size: product.serving_size || "",
      expiry_duration_months: product.expiry_duration_months,
      version: product.version || "",
    })
    setEditErrors({})
  }

  const cancelEditing = () => {
    setEditingProductId(null)
    setEditValues(null)
    setEditErrors({})
  }

  const validateEditValues = (values: InlineEditValues): Record<string, string> => {
    const errors: Record<string, string> = {}
    if (!values.brand.trim()) errors.brand = "Required"
    if (!values.product_name.trim()) errors.product_name = "Required"
    if (values.expiry_duration_months <= 0) errors.expiry_duration_months = "Must be > 0"
    return errors
  }

  const saveEditing = async () => {
    if (!editingProductId || !editValues) return

    const errors = validateEditValues(editValues)
    if (Object.keys(errors).length > 0) {
      setEditErrors(errors)
      return
    }

    setIsSavingEdit(true)
    try {
      const displayName = generateDisplayName(
        editValues.brand,
        editValues.product_name,
        editValues.flavor,
        undefined,
        editValues.version
      )

      await updateMutation.mutateAsync({
        id: editingProductId,
        data: {
          brand: editValues.brand,
          product_name: editValues.product_name,
          flavor: editValues.flavor || undefined,
          serving_size: editValues.serving_size || undefined,
          expiry_duration_months: editValues.expiry_duration_months,
          version: editValues.version || undefined,
          display_name: displayName,
        },
      })
      setEditingProductId(null)
      setEditValues(null)
      setEditErrors({})
    } catch {
      // Error handled by mutation
    } finally {
      setIsSavingEdit(false)
    }
  }

  // Handle blur - auto-save when clicking outside
  const handleEditRowBlur = (e: React.FocusEvent) => {
    // Check if the new focus target is still within the edit row
    const relatedTarget = e.relatedTarget as HTMLElement
    if (editRowRef.current && !editRowRef.current.contains(relatedTarget)) {
      saveEditing()
    }
  }

  // Inline add row handlers
  const resetAddRow = () => {
    setAddRowValues({
      brand: "",
      product_name: "",
      flavor: "",
      serving_size: "",
      expiry_duration_months: 36,
      version: "",
    })
    setAddRowErrors({})
  }

  const cancelAddRow = () => {
    setShowAddRow(false)
    resetAddRow()
  }

  const saveAddRow = async () => {
    const errors = validateEditValues(addRowValues)
    if (Object.keys(errors).length > 0) {
      setAddRowErrors(errors)
      return
    }

    setIsSavingAdd(true)
    try {
      const displayName = generateDisplayName(
        addRowValues.brand,
        addRowValues.product_name,
        addRowValues.flavor,
        undefined,
        addRowValues.version
      )

      await createMutation.mutateAsync({
        brand: addRowValues.brand,
        product_name: addRowValues.product_name,
        flavor: addRowValues.flavor || undefined,
        serving_size: addRowValues.serving_size || undefined,
        expiry_duration_months: addRowValues.expiry_duration_months,
        version: addRowValues.version || undefined,
        display_name: displayName,
      })
      resetAddRow()
      setShowAddRow(false)
    } catch {
      // Error handled by mutation
    } finally {
      setIsSavingAdd(false)
    }
  }

  // Handle blur on add row - auto-save when clicking outside
  const handleAddRowBlur = (e: React.FocusEvent) => {
    const relatedTarget = e.relatedTarget as HTMLElement
    if (addRowRef.current && !addRowRef.current.contains(relatedTarget)) {
      // Only auto-save if there's something to save
      if (addRowValues.brand.trim() || addRowValues.product_name.trim()) {
        saveAddRow()
      } else {
        cancelAddRow()
      }
    }
  }

  // Keyboard navigation for edit row
  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      cancelEditing()
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      saveEditing()
    }
    // Tab is handled natively by browser
  }

  // Keyboard navigation for add row
  const handleAddKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      cancelAddRow()
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      saveAddRow()
    }
    // Tab is handled natively by browser
  }

  const openArchiveDialog = (product: Product) => {
    setArchiveDialogProduct(product)
    setArchiveReason("")
  }

  const handleArchive = async () => {
    if (!archiveDialogProduct || !archiveReason.trim()) return

    try {
      await archiveMutation.mutateAsync({
        id: archiveDialogProduct.id,
        reason: archiveReason.trim(),
      })
      setArchiveDialogProduct(null)
      setArchiveReason("")
    } catch {
      // Error handled by mutation
    }
  }

  // Size management handlers
  const handleAddSize = async (productId: number, size: string) => {
    try {
      await createSizeMutation.mutateAsync({
        productId,
        data: { size },
      })
    } catch (error) {
      console.error("Failed to add size:", error)
    }
  }

  const handleEditSize = async (productId: number, sizeId: number, newSize: string) => {
    try {
      await updateSizeMutation.mutateAsync({
        productId,
        sizeId,
        data: { size: newSize },
      })
    } catch (error) {
      console.error("Failed to update size:", error)
    }
  }

  const handleDeleteSize = async (productId: number, sizeId: number) => {
    try {
      await deleteSizeMutation.mutateAsync({
        productId,
        sizeId,
      })
    } catch (error) {
      console.error("Failed to delete size:", error)
    }
  }

  const openTestSpecsDialog = (product: Product) => {
    setSelectedProductForSpecs(product)
    // Reset add row state
    setAddRowTestType(null)
    setAddRowSpecification("")
    setAddRowRequired(true)
    setEditingSpecCell(null)
    setIsTestSpecsDialogOpen(true)
  }

  // Handle ?editSpecs=<productId> URL param (from Create Sample spec preview)
  useEffect(() => {
    const editSpecsId = searchParams.get('editSpecs')
    if (!editSpecsId || isLoading) return

    const productId = parseInt(editSpecsId, 10)
    if (isNaN(productId)) {
      setSearchParams({}, { replace: true })
      return
    }

    // Try current page first, fall back to API fetch
    const localProduct = data?.items?.find(p => p.id === productId)
    if (localProduct) {
      openTestSpecsDialog(localProduct)
      setSearchParams({}, { replace: true })
    } else {
      productsApi.get(productId).then(product => {
        openTestSpecsDialog(product)
      }).catch(() => {
        // Product not found, silently ignore
      }).finally(() => {
        setSearchParams({}, { replace: true })
      })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, isLoading, data?.items])

  // Handler for selecting test type in add row
  const handleAddRowSelectTestType = (labTest: LabTestType) => {
    setAddRowTestType(labTest)
    setAddRowSpecification(labTest.default_specification || "")
  }

  const handleAddRowClearTestType = () => {
    setAddRowTestType(null)
    setAddRowSpecification("")
    setAddRowRequired(true)
  }

  // Create new test spec from inline add row
  const handleInlineCreateTestSpec = useCallback(async () => {
    if (!selectedProductForSpecs || !addRowTestType) return

    // Use user-entered specification, or fall back to default from test type
    const effectiveSpec = addRowSpecification.trim() || addRowTestType.default_specification || ''
    if (!effectiveSpec) return

    try {
      await createTestSpecMutation.mutateAsync({
        productId: selectedProductForSpecs.id,
        data: {
          lab_test_type_id: addRowTestType.id,
          specification: effectiveSpec,
          is_required: addRowRequired,
        },
      })
      // Clear add row for next entry
      setAddRowTestType(null)
      setAddRowSpecification("")
      setAddRowRequired(true)
      // Focus back to test type for next entry
      setTimeout(() => {
        addRowTestTypeRef.current?.focus()
      }, 50)
    } catch {
      // Error handled by mutation
    }
  }, [selectedProductForSpecs, addRowTestType, addRowSpecification, addRowRequired, createTestSpecMutation])

  const handleDeleteTestSpec = async (specId: number) => {
    if (!selectedProductForSpecs) return
    if (confirm("Are you sure you want to remove this test specification?")) {
      await deleteTestSpecMutation.mutateAsync({
        productId: selectedProductForSpecs.id,
        specId,
      })
    }
  }

  const handleToggleRequired = async (spec: ProductTestSpecification) => {
    if (!selectedProductForSpecs) return
    await updateTestSpecMutation.mutateAsync({
      productId: selectedProductForSpecs.id,
      specId: spec.id,
      data: { is_required: !spec.is_required },
    })
  }

  // Build table data: existing specs only (add row rendered separately)
  const testSpecTableData = useMemo<TestSpecRow[]>(() => {
    return (testSpecs || []).map((spec) => ({
      id: spec.id,
      lab_test_type_id: spec.lab_test_type_id,
      test_name: spec.test_name,
      test_method: spec.test_method,
      test_category: spec.test_category,
      test_unit: spec.test_unit,
      specification: spec.specification,
      is_required: spec.is_required,
      isAddRow: false,
    }))
  }, [testSpecs])

  // TanStack Table columns for Test Specifications (existing rows only)
  const testSpecColumnHelper = createColumnHelper<TestSpecRow>()
  const testSpecColumns = useMemo(() => [
    testSpecColumnHelper.accessor('test_name', {
      header: 'Test Name',
      size: 220,
      cell: (info) => {
        const row = info.row.original
        return (
          <div>
            <p className="font-semibold text-slate-900 text-[14px]">{row.test_name}</p>
            {row.test_method && (
              <p className="text-[11px] text-slate-400 mt-0.5">{row.test_method}</p>
            )}
          </div>
        )
      },
    }),
    testSpecColumnHelper.accessor('test_category', {
      header: 'Category',
      size: 130,
      cell: (info) => {
        const row = info.row.original
        if (!row.test_category) {
          return <span className="text-slate-400 text-[12px] italic">—</span>
        }
        return (
          <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-blue-100 text-blue-700">
            {row.test_category}
          </span>
        )
      },
    }),
    testSpecColumnHelper.accessor('specification', {
      header: 'Specification',
      size: 180,
      cell: (info) => {
        const row = info.row.original
        const isEditing = editingSpecCell?.rowId === Number(row.id) && editingSpecCell?.columnId === 'specification'

        if (isEditing) {
          return (
            <input
              type="text"
              defaultValue={row.specification}
              onBlur={async (e) => {
                const newValue = e.target.value.trim()
                if (newValue && newValue !== row.specification && selectedProductForSpecs) {
                  await updateTestSpecMutation.mutateAsync({
                    productId: selectedProductForSpecs.id,
                    specId: row.id as number,
                    data: { specification: newValue },
                  })
                }
                setEditingSpecCell(null)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  ;(e.target as HTMLInputElement).blur()
                } else if (e.key === 'Escape') {
                  setEditingSpecCell(null)
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingSpecCell({ rowId: row.id as number, columnId: 'specification' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm font-mono"
          >
            {row.specification}
            {row.test_unit && <span className="text-slate-500 ml-1">{row.test_unit}</span>}
          </div>
        )
      },
    }),
    testSpecColumnHelper.accessor('is_required', {
      header: 'Required',
      size: 100,
      cell: (info) => {
        const row = info.row.original
        return (
          <button
            onClick={() => handleToggleRequired(row as unknown as ProductTestSpecification)}
            className="inline-flex items-center gap-1.5 text-[12px] font-semibold transition-colors"
          >
            {row.is_required ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-600" />
                <span className="text-emerald-700">Required</span>
              </>
            ) : (
              <>
                <X className="h-3.5 w-3.5 text-slate-400" />
                <span className="text-slate-500">Optional</span>
              </>
            )}
          </button>
        )
      },
    }),
    testSpecColumnHelper.display({
      id: 'actions',
      header: '',
      size: 50,
      cell: (info) => {
        const row = info.row.original
        return (
          <button
            onClick={() => handleDeleteTestSpec(row.id as number)}
            disabled={deleteTestSpecMutation.isPending}
            className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            title="Delete test"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )
      },
    }),
  ], [
    editingSpecCell, selectedProductForSpecs,
    handleToggleRequired, handleDeleteTestSpec,
    updateTestSpecMutation, deleteTestSpecMutation
  ])

  const testSpecTable = useReactTable({
    data: testSpecTableData,
    columns: testSpecColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id.toString(),
  })

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
          <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Products</h1>
          <p className="mt-1.5 text-[15px] text-slate-500">Manage your product catalog</p>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search products..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            className="pl-10 h-11 bg-white border-slate-200 rounded-lg shadow-sm focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 transition-shadow"
          />
        </div>
        <span className="text-[14px] font-medium text-slate-500">
          {data?.total ?? 0} products
        </span>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
          </div>
        ) : data?.items.length === 0 ? (
          <EmptyState
            icon={Package}
            title="No products found"
            description="Get started by adding your first product"
            actionLabel="Add your first product"
            onAction={() => setShowAddRow(true)}
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Brand</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Product Name</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Flavor</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Sizes</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Serving Size</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Expiry</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Version</TableHead>
                <TableHead className="w-[120px] font-semibold text-slate-600 text-[13px] tracking-wide text-center">Specifications</TableHead>
                <TableHead className="w-[100px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((product) => {
                const isEditing = editingProductId === product.id

                if (isEditing && editValues) {
                  // Editing row
                  return (
                    <TableRow
                      key={product.id}
                      ref={editRowRef}
                      onBlur={handleEditRowBlur}
                      onKeyDown={handleEditKeyDown}
                      className="bg-amber-50/50 transition-colors"
                    >
                      <TableCell>
                        <Input
                          value={editValues.brand}
                          onChange={(e) => setEditValues({ ...editValues, brand: e.target.value })}
                          className={`h-8 text-[14px] ${editErrors.brand ? 'border-red-500' : ''}`}
                          placeholder="Brand"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          value={editValues.product_name}
                          onChange={(e) => setEditValues({ ...editValues, product_name: e.target.value })}
                          className={`h-8 text-[14px] ${editErrors.product_name ? 'border-red-500' : ''}`}
                          placeholder="Product Name"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          value={editValues.flavor}
                          onChange={(e) => setEditValues({ ...editValues, flavor: e.target.value })}
                          className="h-8 text-[14px]"
                          placeholder="Flavor"
                        />
                      </TableCell>
                      <TableCell>
                        <SizeChips
                          sizes={product.sizes}
                          productId={product.id}
                          onAddSize={handleAddSize}
                          onEditSize={handleEditSize}
                          onDeleteSize={handleDeleteSize}
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          value={editValues.serving_size}
                          onChange={(e) => setEditValues({ ...editValues, serving_size: e.target.value })}
                          className="h-8 text-[14px]"
                          placeholder="Serving"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          value={editValues.expiry_duration_months}
                          onChange={(e) => setEditValues({ ...editValues, expiry_duration_months: parseInt(e.target.value) || 0 })}
                          className={`h-8 w-16 text-[14px] ${editErrors.expiry_duration_months ? 'border-red-500' : ''}`}
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          value={editValues.version}
                          onChange={(e) => setEditValues({ ...editValues, version: e.target.value })}
                          className="h-8 w-16 text-[14px]"
                          placeholder="v1"
                        />
                      </TableCell>
                      <TableCell className="text-center">
                        <TestSpecsTooltip
                          productId={product.id}
                          onClick={() => openTestSpecsDialog(product)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-0.5">
                          {isSavingEdit ? (
                            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                          ) : (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={saveEditing}
                                className="h-8 w-8 p-0 text-green-600 hover:text-green-700 hover:bg-green-50 rounded-lg transition-colors"
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={cancelEditing}
                                className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                }

                // Normal display row
                return (
                  <TableRow key={product.id} className="hover:bg-slate-50/50 transition-colors">
                    <TableCell className="font-semibold text-slate-900 text-[14px]">{product.brand}</TableCell>
                    <TableCell className="text-slate-700 text-[14px]">{product.product_name}</TableCell>
                    <TableCell className="text-slate-500 text-[14px]">{product.flavor || "-"}</TableCell>
                    <TableCell>
                      <SizeChips
                        sizes={product.sizes}
                        productId={product.id}
                        onAddSize={handleAddSize}
                        onEditSize={handleEditSize}
                        onDeleteSize={handleDeleteSize}
                      />
                    </TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {product.serving_size || "-"}
                    </TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {product.expiry_duration_months} mo
                    </TableCell>
                    <TableCell className="text-slate-500 text-[14px]">
                      {product.version || "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      <TestSpecsTooltip
                        productId={product.id}
                        onClick={() => openTestSpecsDialog(product)}
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-0.5">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => startEditing(product)}
                          className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        {isAdmin && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openArchiveDialog(product)}
                            disabled={archiveMutation.isPending}
                            className="h-8 w-8 p-0 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                            title="Archive product"
                          >
                            <Archive className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}

              {/* Add Row */}
              {showAddRow && (
                <TableRow
                  ref={addRowRef}
                  onBlur={handleAddRowBlur}
                  onKeyDown={handleAddKeyDown}
                  className="bg-blue-50/50 transition-colors"
                >
                  <TableCell>
                    <Input
                      ref={addRowBrandInputRef}
                      value={addRowValues.brand}
                      onChange={(e) => setAddRowValues({ ...addRowValues, brand: e.target.value })}
                      className={`h-8 text-[14px] ${addRowErrors.brand ? 'border-red-500' : ''}`}
                      placeholder="Brand *"
                      autoFocus
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={addRowValues.product_name}
                      onChange={(e) => setAddRowValues({ ...addRowValues, product_name: e.target.value })}
                      className={`h-8 text-[14px] ${addRowErrors.product_name ? 'border-red-500' : ''}`}
                      placeholder="Product Name *"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={addRowValues.flavor}
                      onChange={(e) => setAddRowValues({ ...addRowValues, flavor: e.target.value })}
                      className="h-8 text-[14px]"
                      placeholder="Flavor"
                    />
                  </TableCell>
                  <TableCell>
                    <span className="text-slate-400 text-[12px]">-</span>
                  </TableCell>
                  <TableCell>
                    <Input
                      value={addRowValues.serving_size}
                      onChange={(e) => setAddRowValues({ ...addRowValues, serving_size: e.target.value })}
                      className="h-8 text-[14px]"
                      placeholder="Serving"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={addRowValues.expiry_duration_months}
                      onChange={(e) => setAddRowValues({ ...addRowValues, expiry_duration_months: parseInt(e.target.value) || 0 })}
                      className="h-8 w-16 text-[14px]"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={addRowValues.version}
                      onChange={(e) => setAddRowValues({ ...addRowValues, version: e.target.value })}
                      className="h-8 w-16 text-[14px]"
                      placeholder="v1"
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <span className="text-slate-400 text-[12px]">-</span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-0.5">
                      {isSavingAdd ? (
                        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                      ) : (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={saveAddRow}
                            className="h-8 w-8 p-0 text-green-600 hover:text-green-700 hover:bg-green-50 rounded-lg transition-colors"
                          >
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={cancelAddRow}
                            className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {/* Add Product Button at Footer */}
        {!showAddRow && (
          <div className="border-t border-slate-100 px-5 py-3">
            <Button
              variant="ghost"
              onClick={() => setShowAddRow(true)}
              className="text-slate-500 hover:text-slate-700 hover:bg-slate-50 h-9 px-3"
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Product
            </Button>
          </div>
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

      {/* Test Specifications Dialog */}
      <Dialog open={isTestSpecsDialogOpen} onOpenChange={setIsTestSpecsDialogOpen}>
        <DialogContent className="sm:max-w-4xl max-h-[85vh] overflow-y-auto p-8">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">Test Specifications</DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              {selectedProductForSpecs?.display_name} - Configure required and optional tests
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <p className="text-[13px] text-slate-500">
              {testSpecs?.length ?? 0} test{(testSpecs?.length ?? 0) !== 1 ? "s" : ""} configured
            </p>

            {/* TanStack Table with inline add row */}
            <div className="rounded-xl border border-slate-200/60 overflow-hidden">
              <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80">
                    {testSpecTable.getHeaderGroups().map((headerGroup) =>
                      headerGroup.headers.map((header) => (
                        <th
                          key={header.id}
                          style={{ width: header.getSize() }}
                          className="text-left font-semibold text-slate-600 text-[13px] tracking-wide px-3 py-2.5"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {testSpecTable.getRowModel().rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors"
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} style={{ width: cell.column.getSize() }} className="px-3 py-2">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {/* Add row - rendered separately with direct state access */}
                  <tr className="bg-emerald-50/60 border-b border-emerald-100 border-dashed">
                    <td style={{ width: 220 }} className="px-3 py-2">
                      <LabTestTypeAutocomplete
                        labTestTypes={labTestTypes?.items || []}
                        excludeIds={testSpecs?.map(s => s.lab_test_type_id) || []}
                        value={addRowTestType}
                        onSelect={handleAddRowSelectTestType}
                        onClear={handleAddRowClearTestType}
                        placeholder="Search tests..."
                        inputRef={addRowTestTypeRef}
                        onTab={() => addRowSpecInputRef.current?.focus()}
                      />
                    </td>
                    <td style={{ width: 130 }} className="px-3 py-2">
                      {addRowTestType?.test_category ? (
                        <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-blue-100 text-blue-700">
                          {addRowTestType.test_category}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[12px] italic">—</span>
                      )}
                    </td>
                    <td style={{ width: 180 }} className="px-3 py-2">
                      <input
                        ref={addRowSpecInputRef}
                        type="text"
                        value={addRowSpecification}
                        onChange={(e) => setAddRowSpecification(e.target.value)}
                        onKeyDown={(e) => {
                          const effectiveSpec = addRowSpecification.trim() || addRowTestType?.default_specification || ''
                          if (e.key === 'Enter' && addRowTestType && effectiveSpec) {
                            e.preventDefault()
                            handleInlineCreateTestSpec()
                          } else if (e.key === 'Tab' && !e.shiftKey) {
                            e.preventDefault()
                            addRowRequiredRef.current?.focus()
                          }
                        }}
                        placeholder="e.g., < 5000 CFU/g"
                        className="w-full px-2 py-1 text-sm border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                        disabled={!addRowTestType}
                      />
                    </td>
                    <td style={{ width: 100 }} className="px-3 py-2">
                      <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                          ref={addRowRequiredRef}
                          type="checkbox"
                          checked={addRowRequired}
                          onChange={(e) => setAddRowRequired(e.target.checked)}
                          disabled={!addRowTestType}
                          className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
                        />
                        <span className={`text-[12px] ${addRowTestType ? 'text-slate-700' : 'text-slate-400'}`}>
                          Required
                        </span>
                      </label>
                    </td>
                    <td style={{ width: 50 }} className="px-3 py-2">
                      {(() => {
                        const effectiveSpec = addRowSpecification.trim() || addRowTestType?.default_specification || ''
                        const isReady = !!addRowTestType && !!effectiveSpec
                        const tooltipText = !addRowTestType
                          ? "Select a test type first"
                          : !effectiveSpec
                            ? "Enter a specification to add"
                            : "Add test"
                        return (
                          <TooltipProvider delayDuration={0}>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button
                                  type="button"
                                  onClick={handleInlineCreateTestSpec}
                                  disabled={!isReady || createTestSpecMutation.isPending}
                                  className={`p-1.5 rounded-lg transition-colors ${
                                    isReady
                                      ? 'text-emerald-600 bg-emerald-100 hover:bg-emerald-200'
                                      : 'text-slate-300 hover:text-slate-400 disabled:cursor-not-allowed'
                                  }`}
                                >
                                  {createTestSpecMutation.isPending ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <Plus className="h-4 w-4" />
                                  )}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="left" className="text-xs">
                                {tooltipText}
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        )
                      })()}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {testSpecs?.length === 0 && !addRowTestType && (
              <div className="flex items-center justify-center gap-2 py-3 text-emerald-600">
                <Plus className="h-4 w-4" />
                <p className="text-[13px] font-medium">
                  Use the row above to add your first test specification
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="pt-4 flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                // Clear pending add row and close
                setAddRowTestType(null)
                setAddRowSpecification("")
                setAddRowRequired(true)
                setIsTestSpecsDialogOpen(false)
                setSelectedProductForSpecs(null)
              }}
              className="border-slate-200 h-10"
            >
              Close
            </Button>
            <Button
              type="button"
              onClick={async () => {
                // Save pending add row if valid, then close
                if (addRowTestType && addRowSpecification.trim()) {
                  await handleInlineCreateTestSpec()
                }
                setIsTestSpecsDialogOpen(false)
                setSelectedProductForSpecs(null)
              }}
              disabled={createTestSpecMutation.isPending}
              className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
            >
              {createTestSpecMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save & Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Archive Confirmation Dialog */}
      <Dialog open={!!archiveDialogProduct} onOpenChange={() => setArchiveDialogProduct(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">
              Archive Product
            </DialogTitle>
            <DialogDescription className="text-slate-500">
              You are archiving "{archiveDialogProduct?.display_name}". This product will no longer be available for new samples.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="archiveReason" className="text-sm font-medium text-slate-700">
                Reason for archiving <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="archiveReason"
                value={archiveReason}
                onChange={(e) => setArchiveReason(e.target.value)}
                placeholder="e.g., Discontinued by manufacturer, replaced by new version..."
                className="min-h-[80px] resize-none"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => setArchiveDialogProduct(null)}
              disabled={archiveMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleArchive}
              disabled={archiveMutation.isPending || !archiveReason.trim()}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {archiveMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Archiving...
                </>
              ) : (
                <>
                  <Archive className="mr-2 h-4 w-4" />
                  Archive Product
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      </motion.div>
    </div>
  )
}
