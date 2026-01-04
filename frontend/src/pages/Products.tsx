import { useState, useRef, useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Pencil, Trash2, Search, Loader2, Package, ArrowRight, FlaskConical, Check, X, ChevronDown } from "lucide-react"
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

export function ProductsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState("")
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [isBulkImportOpen, setIsBulkImportOpen] = useState(false)

  // Test specs dialog state
  const [isTestSpecsDialogOpen, setIsTestSpecsDialogOpen] = useState(false)
  const [selectedProductForSpecs, setSelectedProductForSpecs] = useState<Product | null>(null)
  const [selectedTestType, setSelectedTestType] = useState<LabTestType | null>(null)
  const [testSpecification, setTestSpecification] = useState("")
  const [isRequired, setIsRequired] = useState(true)
  const [isEditTestDialogOpen, setIsEditTestDialogOpen] = useState(false)
  const [selectedTestSpec, setSelectedTestSpec] = useState<ProductTestSpecification | null>(null)

  const { data, isLoading } = useProducts({ page, page_size: 50, search: search || undefined })
  const createMutation = useCreateProduct()
  const updateMutation = useUpdateProduct()
  const deleteMutation = useDeleteProduct()

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

  // Size management handlers (placeholder until backend supports multi-size)
  const handleAddSize = (productId: number, size: string) => {
    // TODO: Implement when backend supports multi-size
    console.log(`Add size "${size}" to product ${productId}`)
    alert(`Size "${size}" will be saved when backend is ready. For now, edit the product to change the size.`)
  }

  const handleEditSize = (productId: number, sizeId: number, newSize: string) => {
    // TODO: Implement when backend supports multi-size
    console.log(`Edit size ${sizeId} to "${newSize}" for product ${productId}`)
    alert(`Size edit will be saved when backend is ready. For now, edit the product to change the size.`)
  }

  const handleDeleteSize = (productId: number, sizeId: number) => {
    // TODO: Implement when backend supports multi-size
    console.log(`Delete size ${sizeId} from product ${productId}`)
    alert(`Size delete will be saved when backend is ready. For now, edit the product to change the size.`)
  }

  const openTestSpecsDialog = (product: Product) => {
    setSelectedProductForSpecs(product)
    setSelectedTestType(null)
    setTestSpecification("")
    setIsRequired(true)
    setIsTestSpecsDialogOpen(true)
  }

  const handleSelectTestType = (labTest: LabTestType) => {
    setSelectedTestType(labTest)
    setTestSpecification(labTest.default_specification || "")
  }

  const handleClearTestType = () => {
    setSelectedTestType(null)
    setTestSpecification("")
    setIsRequired(true)
  }

  const handleCreateTestSpec = async () => {
    if (!selectedProductForSpecs || !selectedTestType) return

    try {
      await createTestSpecMutation.mutateAsync({
        productId: selectedProductForSpecs.id,
        data: {
          lab_test_type_id: selectedTestType.id,
          specification: testSpecification,
          is_required: isRequired,
        },
      })
      // Clear fields for next entry
      setSelectedTestType(null)
      setTestSpecification("")
      setIsRequired(true)
    } catch {
      // Error handled by mutation
    }
  }

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

  const openEditTestDialog = (spec: ProductTestSpecification) => {
    setSelectedTestSpec(spec)
    setTestSpecification(spec.specification)
    setIsRequired(spec.is_required)
    setIsEditTestDialogOpen(true)
  }

  const handleUpdateTestSpec = async () => {
    if (!selectedProductForSpecs || !selectedTestSpec) return

    try {
      await updateTestSpecMutation.mutateAsync({
        productId: selectedProductForSpecs.id,
        specId: selectedTestSpec.id,
        data: {
          specification: testSpecification,
          is_required: isRequired,
        },
      })
      setIsEditTestDialogOpen(false)
      setSelectedTestSpec(null)
      setTestSpecification("")
    } catch {
      // Error handled by mutation
    }
  }

  const isMutating = createMutation.isPending || updateMutation.isPending

  return (
    <div className="space-y-8">
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
            {/* Inline add test row - all 4 elements always visible */}
            <div className="flex items-center gap-3">
              <div className="flex-1 max-w-[240px]">
                <LabTestTypeAutocomplete
                  labTestTypes={labTestTypes?.items || []}
                  excludeIds={testSpecs?.map(s => s.lab_test_type_id) || []}
                  value={selectedTestType}
                  onSelect={handleSelectTestType}
                  onClear={handleClearTestType}
                  placeholder="Search tests..."
                />
              </div>

              <Input
                value={testSpecification}
                onChange={(e) => setTestSpecification(e.target.value)}
                placeholder="Specification..."
                className="w-44 h-9"
                disabled={!selectedTestType}
              />

              <label className="flex items-center gap-1.5 text-sm whitespace-nowrap text-slate-700">
                <input
                  type="checkbox"
                  checked={isRequired}
                  onChange={(e) => setIsRequired(e.target.checked)}
                  disabled={!selectedTestType}
                  className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
                />
                Required
              </label>

              <Button
                size="sm"
                onClick={handleCreateTestSpec}
                disabled={!selectedTestType || !testSpecification || createTestSpecMutation.isPending}
                className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-9"
              >
                {createTestSpecMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Plus className="mr-1 h-4 w-4" />
                    Add
                  </>
                )}
              </Button>
            </div>

            <p className="text-[13px] text-slate-500 mt-2">
              {testSpecs?.length ?? 0} test{(testSpecs?.length ?? 0) !== 1 ? "s" : ""} configured
            </p>

            {testSpecs && testSpecs.length > 0 ? (
              <div className="rounded-xl border border-slate-200/60 overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/80 hover:bg-slate-50/80 border-b border-slate-100">
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Test Name</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Category</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Specification</TableHead>
                      <TableHead className="font-semibold text-slate-600 text-[13px] tracking-wide">Required</TableHead>
                      <TableHead className="w-[50px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {testSpecs.map((spec) => (
                      <TableRow key={spec.id} className="hover:bg-slate-50/50 transition-colors">
                        <TableCell>
                          <div>
                            <p className="font-semibold text-slate-900 text-[14px]">{spec.test_name}</p>
                            {spec.test_method && (
                              <p className="text-[11px] text-slate-400 mt-0.5">{spec.test_method}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide bg-blue-100 text-blue-700">
                            {spec.test_category}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <code className="text-[13px] text-slate-700 font-mono flex-1">
                              {spec.specification}
                              {spec.test_unit && <span className="text-slate-500 ml-1">{spec.test_unit}</span>}
                            </code>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditTestDialog(spec)}
                              disabled={updateTestSpecMutation.isPending}
                              className="h-7 w-7 p-0 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors flex-shrink-0"
                              title="Edit specification"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                        <TableCell>
                          <button
                            onClick={() => handleToggleRequired(spec)}
                            className="inline-flex items-center gap-1.5 text-[12px] font-semibold transition-colors"
                          >
                            {spec.is_required ? (
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
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteTestSpec(spec.id)}
                            disabled={deleteTestSpecMutation.isPending}
                            className="h-8 w-8 p-0 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Delete specification"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="text-center py-10 rounded-xl border border-slate-200/60 bg-slate-50/30">
                <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 flex items-center justify-center">
                  <FlaskConical className="h-7 w-7 text-slate-400" />
                </div>
                <p className="mt-4 text-[14px] font-medium text-slate-600">No test specifications configured</p>
                <p className="mt-1 text-[13px] text-slate-500">Add tests from the catalog to define quality requirements</p>
              </div>
            )}
          </div>

          <DialogFooter className="pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsTestSpecsDialogOpen(false)
                setSelectedProductForSpecs(null)
              }}
              className="border-slate-200 h-10"
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Test Specification Dialog */}
      <Dialog open={isEditTestDialogOpen} onOpenChange={setIsEditTestDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">Edit Test Specification</DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              Update the specification and requirements
            </DialogDescription>
          </DialogHeader>

          {selectedTestSpec && (
            <div className="space-y-4 mt-2">
              <div className="rounded-xl bg-blue-50/50 border border-blue-200/60 p-4">
                <p className="font-semibold text-slate-900 text-[14px]">{selectedTestSpec.test_name}</p>
                <p className="text-[12px] text-slate-500 mt-0.5">{selectedTestSpec.test_category}</p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="edit-specification" className="text-[13px] font-semibold text-slate-700">
                  Specification *
                </Label>
                <Input
                  id="edit-specification"
                  value={testSpecification}
                  onChange={(e) => setTestSpecification(e.target.value)}
                  placeholder="e.g., < 10,000 CFU/g, Negative"
                  className="border-slate-200 h-10"
                />
              </div>

              <div className="flex items-center gap-2.5">
                <input
                  id="edit-is-required"
                  type="checkbox"
                  checked={isRequired}
                  onChange={(e) => setIsRequired(e.target.checked)}
                  className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
                />
                <Label htmlFor="edit-is-required" className="font-normal text-[14px] text-slate-700">
                  Mark as required test
                </Label>
              </div>

              <DialogFooter className="flex gap-2 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setIsEditTestDialogOpen(false)
                    setSelectedTestSpec(null)
                    setTestSpecification("")
                  }}
                  className="border-slate-200 h-10"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={handleUpdateTestSpec}
                  disabled={!testSpecification || updateTestSpecMutation.isPending}
                  className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
                >
                  {updateTestSpecMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Changes
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
