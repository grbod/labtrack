import { useState, useRef, useEffect, useMemo, useCallback } from "react"
import { motion } from "framer-motion"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2, Package, ArrowRight, Check, X, ChevronDown } from "lucide-react"
import { useReactTable, getCoreRowModel, createColumnHelper, flexRender } from "@tanstack/react-table"
import { TestSpecsTooltip } from "@/components/domain/TestSpecsTooltip"
import { LabTestTypeAutocomplete } from "@/components/form/LabTestTypeAutocomplete"
import { generateDisplayName } from "@/lib/product-utils"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ProductBulkImport } from "@/components/bulk-import/ProductBulkImport"

import {
  useProducts,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
  useCreateSize,
  useUpdateSize,
  useDeleteSize,
  useProductTestSpecs,
  useCreateTestSpec,
  useUpdateTestSpec,
  useDeleteTestSpec,
} from "@/hooks/useProducts"
import { useLabTestTypes } from "@/hooks/useLabTestTypes"
import type { Product, ProductSize, ProductTestSpecification, LabTestType } from "@/types"
import type { CreateProductData } from "@/api/products"

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

const productSchema = z.object({
  brand: z.string().min(1, "Brand is required"),
  product_name: z.string().min(1, "Product name is required"),
  flavor: z.string().optional(),
  version: z.string().optional(),
  serving_size: z.string().optional(),
  expiry_duration_months: z.number().int().positive(),
})

type ProductForm = z.infer<typeof productSchema>

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

export function ProductsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [isBulkImportOpen, setIsBulkImportOpen] = useState(false)

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

  const { data, isLoading } = useProducts({ page, page_size: 50, search: search || undefined })
  const createMutation = useCreateProduct()
  const updateMutation = useUpdateProduct()
  const deleteMutation = useDeleteProduct()

  // Size mutation hooks
  const createSizeMutation = useCreateSize()
  const updateSizeMutation = useUpdateSize()
  const deleteSizeMutation = useDeleteSize()

  // Test specs hooks
  const { data: testSpecs } = useProductTestSpecs(selectedProductForSpecs?.id ?? 0)
  const { data: labTestTypes } = useLabTestTypes({ page_size: 100 })
  const createTestSpecMutation = useCreateTestSpec()
  const updateTestSpecMutation = useUpdateTestSpec()
  const deleteTestSpecMutation = useDeleteTestSpec()

  const form = useForm<ProductForm>({
    resolver: zodResolver(productSchema),
    defaultValues: {
      expiry_duration_months: 36,
    },
  })

  const { register, handleSubmit, reset, formState: { errors }, watch } = form

  // Watch fields for live display name preview
  const watchedBrand = watch("brand", "")
  const watchedProductName = watch("product_name", "")
  const watchedFlavor = watch("flavor", "")
  const watchedVersion = watch("version", "")

  const previewDisplayName = generateDisplayName(
    watchedBrand,
    watchedProductName,
    watchedFlavor,
    undefined, // Size is now managed separately via chips
    watchedVersion
  )

  const openCreateDialog = () => {
    setEditingProduct(null)
    reset({
      brand: "",
      product_name: "",
      flavor: "",
      version: "",
      serving_size: "",
      expiry_duration_months: 36,
    })
    setIsDialogOpen(true)
  }

  // Extract version from existing display name (if it ends with (VX))
  const extractVersion = (displayName: string): string => {
    const match = displayName.match(/\(V(\d+)\)$/)
    return match ? match[1] : ""
  }

  const openEditDialog = (product: Product) => {
    setEditingProduct(product)
    reset({
      brand: product.brand,
      product_name: product.product_name,
      flavor: product.flavor || "",
      version: extractVersion(product.display_name),
      serving_size: product.serving_size || "",
      expiry_duration_months: product.expiry_duration_months,
    })
    setIsDialogOpen(true)
  }

  const onSubmit = async (formData: ProductForm) => {
    // Auto-generate display name from fields (size is managed separately via chips)
    const displayName = generateDisplayName(
      formData.brand,
      formData.product_name,
      formData.flavor,
      undefined, // Size is managed separately
      formData.version
    )

    const data: CreateProductData = {
      brand: formData.brand,
      product_name: formData.product_name,
      display_name: displayName,
      flavor: formData.flavor || undefined,
      // Note: size is now managed via inline chips, not in the edit dialog
      serving_size: formData.serving_size || undefined,
      expiry_duration_months: formData.expiry_duration_months,
    }

    try {
      if (editingProduct) {
        await updateMutation.mutateAsync({ id: editingProduct.id, data })
      } else {
        await createMutation.mutateAsync(data)
      }
      setIsDialogOpen(false)
    } catch {
      // Error handled by mutation
    }
  }

  const handleDelete = async (id: number) => {
    if (confirm("Are you sure you want to delete this product?")) {
      await deleteMutation.mutateAsync(id)
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
    if (!selectedProductForSpecs || !addRowTestType || !addRowSpecification.trim()) return

    try {
      await createTestSpecMutation.mutateAsync({
        productId: selectedProductForSpecs.id,
        data: {
          lab_test_type_id: addRowTestType.id,
          specification: addRowSpecification,
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

  const isMutating = createMutation.isPending || updateMutation.isPending

  // Build table data: existing specs + add row
  const testSpecTableData = useMemo<TestSpecRow[]>(() => {
    const existingRows: TestSpecRow[] = (testSpecs || []).map((spec) => ({
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

    // Add empty "add" row at the bottom
    const addRow: TestSpecRow = {
      id: 'new',
      lab_test_type_id: addRowTestType?.id ?? null,
      test_name: addRowTestType?.test_name ?? '',
      test_method: addRowTestType?.test_method ?? null,
      test_category: addRowTestType?.test_category ?? null,
      test_unit: addRowTestType?.default_unit ?? null,
      specification: addRowSpecification,
      is_required: addRowRequired,
      isAddRow: true,
    }

    return [...existingRows, addRow]
  }, [testSpecs, addRowTestType, addRowSpecification, addRowRequired])

  // TanStack Table columns for Test Specifications
  const testSpecColumnHelper = createColumnHelper<TestSpecRow>()
  const testSpecColumns = useMemo(() => [
    testSpecColumnHelper.accessor('test_name', {
      header: 'Test Name',
      size: 220,
      cell: (info) => {
        const row = info.row.original

        if (row.isAddRow) {
          // Add row - show autocomplete
          return (
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
          )
        }

        // Existing row - display test name
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
        if ((row.isAddRow && !row.lab_test_type_id) || !row.test_category) {
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

        if (row.isAddRow) {
          // Add row - show input (always editable)
          return (
            <input
              ref={addRowSpecInputRef}
              type="text"
              value={addRowSpecification}
              onChange={(e) => setAddRowSpecification(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && addRowTestType && addRowSpecification.trim()) {
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
          )
        }

        // Existing row - show inline editable
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

        if (row.isAddRow) {
          return (
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                ref={addRowRequiredRef}
                type="checkbox"
                checked={addRowRequired}
                onChange={(e) => setAddRowRequired(e.target.checked)}
                onKeyDown={(e) => {
                  if (e.key === 'Tab' && !e.shiftKey) {
                    e.preventDefault()
                    // Auto-save if valid, then focus back to test type
                    if (addRowTestType && addRowSpecification.trim()) {
                      handleInlineCreateTestSpec()
                    }
                  }
                }}
                disabled={!addRowTestType}
                className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
              />
              <span className={`text-[12px] ${addRowTestType ? 'text-slate-700' : 'text-slate-400'}`}>
                Required
              </span>
            </label>
          )
        }

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

        if (row.isAddRow) {
          // Show add button for add row
          return (
            <button
              onClick={handleInlineCreateTestSpec}
              disabled={!addRowTestType || !addRowSpecification.trim() || createTestSpecMutation.isPending}
              className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title="Add test"
            >
              {createTestSpecMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
            </button>
          )
        }

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
    addRowTestType, addRowSpecification, addRowRequired, editingSpecCell,
    labTestTypes, testSpecs, selectedProductForSpecs,
    handleAddRowSelectTestType, handleAddRowClearTestType, handleInlineCreateTestSpec,
    handleToggleRequired, handleDeleteTestSpec,
    updateTestSpecMutation, createTestSpecMutation, deleteTestSpecMutation
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
        <Button
          onClick={openCreateDialog}
          className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10 px-4"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Product
        </Button>
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

      {/* Bulk Import */}
      <Collapsible open={isBulkImportOpen} onOpenChange={setIsBulkImportOpen}>
        <CollapsibleTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between h-11 bg-white hover:bg-slate-50"
          >
            <span className="font-semibold text-slate-700">📊 Bulk Import Products</span>
            <ChevronDown
              className={`h-4 w-4 transition-transform ${
                isBulkImportOpen ? "rotate-180" : ""
              }`}
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4">
          <div className="rounded-xl border border-slate-200/60 bg-white shadow-sm p-6">
            <ProductBulkImport />
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
              <Package className="h-8 w-8 text-slate-400" />
            </div>
            <p className="mt-5 text-[15px] font-medium text-slate-600">No products found</p>
            <p className="mt-1 text-[14px] text-slate-500">Get started by adding your first product</p>
            <button
              onClick={openCreateDialog}
              className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold text-blue-600 hover:text-blue-700 transition-colors"
            >
              Add your first product
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Brand</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Product Name</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Flavor</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Sizes</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Serving</TableHead>
                <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Expiry</TableHead>
                <TableHead className="w-[120px] font-semibold text-slate-600 text-[13px] tracking-wide text-center">Specifications</TableHead>
                <TableHead className="w-[100px] font-semibold text-slate-600 text-[13px] tracking-wide">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((product) => (
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
                        onClick={() => openEditDialog(product)}
                        className="h-8 w-8 p-0 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(product.id)}
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
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">
              {editingProduct ? "Edit Product" : "Add Product"}
            </DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              {editingProduct
                ? "Update product information"
                : "Add a new product to the catalog"}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="brand" className="text-[13px] font-semibold text-slate-700">Brand *</Label>
                <Input
                  id="brand"
                  {...register("brand")}
                  aria-invalid={!!errors.brand}
                  className="border-slate-200 h-10"
                />
                {errors.brand && (
                  <p className="text-[13px] text-red-600">{errors.brand.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="product_name" className="text-[13px] font-semibold text-slate-700">Product Name *</Label>
                <Input
                  id="product_name"
                  {...register("product_name")}
                  aria-invalid={!!errors.product_name}
                  className="border-slate-200 h-10"
                />
                {errors.product_name && (
                  <p className="text-[13px] text-red-600">{errors.product_name.message}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-[1fr_80px] gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="flavor" className="text-[13px] font-semibold text-slate-700">Flavor</Label>
                <Input id="flavor" {...register("flavor")} className="border-slate-200 h-10" />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="version" className="text-[13px] font-semibold text-slate-700">Version</Label>
                <Input
                  id="version"
                  {...register("version")}
                  placeholder="1, 2..."
                  className="border-slate-200 h-10"
                />
              </div>
            </div>

            <p className="text-[11px] text-slate-400">
              Sizes are managed in the product table using the inline chips
            </p>

            {/* Display Name Preview */}
            <div className="space-y-1.5">
              <Label className="text-[13px] font-semibold text-slate-500">Display Name (auto-generated)</Label>
              <div className="h-10 px-3 flex items-center rounded-lg border border-slate-300 bg-slate-100 text-[14px] text-slate-500 cursor-not-allowed">
                {previewDisplayName || <span className="text-slate-400 italic">Enter brand and product name...</span>}
              </div>
              <p className="text-[11px] text-slate-400">
                Generated from Brand - Product Name - Flavor (Version)
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="serving_size" className="text-[13px] font-semibold text-slate-700">Serving Size</Label>
                <Input
                  id="serving_size"
                  {...register("serving_size")}
                  placeholder="e.g., 30g, 2 capsules, 1 tsp"
                  className="border-slate-200 h-10"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="expiry_duration_months" className="text-[13px] font-semibold text-slate-700">Expiry (months)</Label>
                <Input
                  id="expiry_duration_months"
                  type="number"
                  {...register("expiry_duration_months", { valueAsNumber: true })}
                  className="border-slate-200 h-10"
                />
              </div>
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
                className="border-slate-200 h-10"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isMutating}
                className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
              >
                {isMutating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingProduct ? "Save Changes" : "Add Product"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Test Specifications Dialog */}
      <Dialog open={isTestSpecsDialogOpen} onOpenChange={setIsTestSpecsDialogOpen}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh] overflow-y-auto">
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
                  {testSpecTable.getRowModel().rows.map((row) => {
                    const isAddRow = row.original.isAddRow
                    return (
                      <tr
                        key={row.id}
                        className={`border-b border-slate-100 transition-colors ${
                          isAddRow ? 'bg-slate-50/50' : 'hover:bg-slate-50/50'
                        }`}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} style={{ width: cell.column.getSize() }} className="px-3 py-2">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {testSpecs?.length === 0 && !addRowTestType && (
              <p className="text-center text-[13px] text-slate-400 py-2">
                Use the row above to add your first test specification
              </p>
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

      </motion.div>
    </div>
  )
}
