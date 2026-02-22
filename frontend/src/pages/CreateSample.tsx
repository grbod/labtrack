import { useState, useCallback, useMemo, useEffect } from "react"
import { motion } from "framer-motion"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Loader2, Package, Beaker, CalendarDays, Trash2, ChevronUp, ChevronDown, Copy, CheckCircle2, Check, Download } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useReactTable, getCoreRowModel, createColumnHelper, flexRender } from "@tanstack/react-table"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ProductAutocomplete } from "@/components/form/ProductAutocomplete"
import { SpecPreviewPanel } from "@/components/domain/SpecPreviewPanel"

import { useProducts } from "@/hooks/useProducts"
import { useCreateLot, useCreateSublotsBulk, useLotWithSpecs } from "@/hooks/useLots"
import { useDownloadLotDaaneCoc, useDownloadLotDaaneCocPdf } from "@/hooks/useDaaneCoc"
import { useLabInfo } from "@/hooks/useLabInfo"
import type { Product, LotType } from "@/types"

// User-selectable lot types (excludes sublot which is created automatically)
type SelectableLotType = "standard" | "parent_lot" | "multi_sku_composite"

const LOT_TYPES: { value: SelectableLotType; label: string; description: string }[] = [
  {
    value: "standard",
    label: "Standard Lot",
    description: "Single product, single lot",
  },
  {
    value: "parent_lot",
    label: "Parent Lot",
    description: "Master Lot with Sub-Batches of same product",
  },
  {
    value: "multi_sku_composite",
    label: "Multi-SKU Composite",
    description: "Multiple products combined",
  },
]

const sampleSchema = z.object({
  lot_number: z.string().min(1, "Lot number is required"),
  lot_type: z.enum(["standard", "parent_lot", "multi_sku_composite"]),
  mfg_date: z.string().optional(),
  exp_date: z.string().optional(),
  reference_number: z.string().optional(),
  generate_coa: z.boolean(),
})

type SampleForm = z.infer<typeof sampleSchema>

interface SelectedProduct {
  product: Product
  percentage?: number
}

// Types for table rows
interface SubBatchRow {
  id: number
  mfg_date: string
  batch_number: string
}

interface CompositeProductRow {
  id: number
  product_id: number | null
  product_name: string
  mfg_date: string
  batch_number: string
}

interface DaaneTestSelectionOption {
  labTestTypeId: number
  testName: string
  testCategory: string | null
  specification: string
}

export function CreateSamplePage() {
  const navigate = useNavigate()
  const [isProductDialogOpen, setIsProductDialogOpen] = useState(false)
  const [selectedProducts, setSelectedProducts] = useState<SelectedProduct[]>([])
  const [productSearch, setProductSearch] = useState("")

  // Standard lot product autocomplete state
  const [standardProductText, setStandardProductText] = useState("")
  const [standardProductTouched, setStandardProductTouched] = useState(false)

  // Parent lot product autocomplete state
  const [parentProductText, setParentProductText] = useState("")
  const [parentProductTouched, setParentProductTouched] = useState(false)

  // Sub-batch state for parent_lot
  const [subBatches, setSubBatches] = useState<SubBatchRow[]>([
    { id: 1, mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
  ])
  const [nextSubBatchId, setNextSubBatchId] = useState(2)
  const [editingSubBatchCell, setEditingSubBatchCell] = useState<{ rowId: number; columnId: string } | null>(null)

  // Composite products state for multi_sku_composite
  const [compositeProducts, setCompositeProducts] = useState<CompositeProductRow[]>([
    { id: 1, product_id: null, product_name: '', mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
  ])
  const [nextCompositeId, setNextCompositeId] = useState(2)
  const [editingCompositeCell, setEditingCompositeCell] = useState<{ rowId: number; columnId: string } | null>(null)

  // Expiration date nudge factor (in days)
  const [expiryNudgeDays, setExpiryNudgeDays] = useState(0)

  // Success dialog state
  const [successData, setSuccessData] = useState<{
    lotId: number
    referenceNumber: string
    brand: string
    productName: string
    flavorSize: string | null  // "Flavor (Size)" or just "Flavor" or "(Size)"
    lotNumber: string
    lotType: string
  } | null>(null)
  const [copied, setCopied] = useState(false)

  // "Add new product" dialog state
  const [showAddProductDialog, setShowAddProductDialog] = useState(false)
  const [isDaanePdfDialogOpen, setIsDaanePdfDialogOpen] = useState(false)
  const [selectedDaaneTestIds, setSelectedDaaneTestIds] = useState<number[]>([])
  const [initializedDaaneSelection, setInitializedDaaneSelection] = useState(false)
  const [daaneSpecialInstructions, setDaaneSpecialInstructions] = useState("")

  // Spec preview panel state
  const [specPreviewProduct, setSpecPreviewProduct] = useState<Product | null>(null)
  const { labInfo } = useLabInfo()

  const showSpecPreview = useCallback((product: Product) => {
    if (labInfo?.show_spec_preview_on_sample) {
      setSpecPreviewProduct(product)
    }
  }, [labInfo?.show_spec_preview_on_sample])

  // Helper to format flavor and size for success dialog
  const formatFlavorSize = (product: { flavor?: string | null; size?: string | null }) => {
    const parts: string[] = []
    if (product.flavor) parts.push(product.flavor)
    if (product.size) parts.push(`(${product.size})`)
    return parts.length > 0 ? parts.join(' ') : null
  }

  const { data: productsData, isLoading: isProductsLoading } = useProducts({ page_size: 100 })
  const createMutation = useCreateLot()
  const createSublotsMutation = useCreateSublotsBulk()
  const {
    data: successLotWithSpecs,
    isLoading: isLoadingSuccessLotWithSpecs,
    isError: isSuccessLotWithSpecsError,
    refetch: refetchSuccessLotWithSpecs,
  } = useLotWithSpecs(successData?.lotId ?? 0)
  const downloadCocMutation = useDownloadLotDaaneCoc()
  const downloadCocPdfMutation = useDownloadLotDaaneCocPdf()

  const form = useForm<SampleForm>({
    resolver: zodResolver(sampleSchema),
    defaultValues: {
      lot_type: "standard",
      generate_coa: true,
    },
  })

  const { register, handleSubmit, watch, setValue, formState: { errors } } = form
  const watchedLotType = watch("lot_type")
  const watchedMfgDate = watch("mfg_date")

  // Helper to calculate expiry date from mfg_date, expiry_duration_months, and optional days nudge
  const calculateExpiryDate = useCallback((mfgDate: string, expiryMonths: number, nudgeDays: number = 0): string => {
    const date = new Date(mfgDate)
    date.setMonth(date.getMonth() + expiryMonths)
    if (nudgeDays !== 0) {
      date.setDate(date.getDate() + nudgeDays)
    }
    return date.toISOString().split('T')[0]
  }, [])

  // Computed exp date for parent_lot (from earliest sub-batch mfg date)
  const parentLotExpDate = useMemo(() => {
    if (watchedLotType !== "parent_lot") return ""
    if (selectedProducts.length === 0 || subBatches.length === 0) return ""
    const validDates = subBatches.filter(sb => sb.mfg_date).map(sb => sb.mfg_date)
    if (validDates.length === 0) return ""
    const earliestMfg = validDates.reduce((min, d) => d < min ? d : min)
    return calculateExpiryDate(earliestMfg, selectedProducts[0].product.expiry_duration_months, expiryNudgeDays)
  }, [watchedLotType, subBatches, selectedProducts, expiryNudgeDays, calculateExpiryDate])

  // Auto-calculate exp_date when mfg_date, product, or nudge changes
  useEffect(() => {
    // For multi_sku_composite, use earliest mfg_date from composite products (no form-level mfg_date)
    if (watchedLotType === "multi_sku_composite") {
      const validProducts = compositeProducts.filter(cp => cp.product_id !== null)
      if (validProducts.length > 0 && productsData?.items) {
        // Find earliest mfg_date from composite products
        const earliestMfgDate = validProducts.reduce((min, cp) =>
          cp.mfg_date < min ? cp.mfg_date : min, validProducts[0].mfg_date)

        // Find shortest expiry duration among selected products
        const minExpiry = validProducts.reduce((min, cp) => {
          const product = productsData.items.find(p => p.id === cp.product_id)
          return product ? Math.min(min, product.expiry_duration_months) : min
        }, Infinity)

        if (minExpiry !== Infinity && earliestMfgDate) {
          setValue("exp_date", calculateExpiryDate(earliestMfgDate, minExpiry, expiryNudgeDays))
        } else {
          setValue("exp_date", "")
        }
      } else {
        setValue("exp_date", "")
      }
      return
    }

    // For STANDARD or parent_lot, use form-level mfg_date
    if (!watchedMfgDate) {
      setValue("exp_date", "")
      return
    }

    if (selectedProducts.length > 0) {
      const expiryMonths = selectedProducts[0].product.expiry_duration_months
      setValue("exp_date", calculateExpiryDate(watchedMfgDate, expiryMonths, expiryNudgeDays))
    }
  }, [watchedMfgDate, selectedProducts, compositeProducts, watchedLotType, productsData, setValue, calculateExpiryDate, expiryNudgeDays])

  const daaneTestSelectionOptions = useMemo<DaaneTestSelectionOption[]>(() => {
    if (!successLotWithSpecs?.products?.length) return []

    const byTestTypeId = new Map<number, DaaneTestSelectionOption>()
    for (const product of successLotWithSpecs.products) {
      for (const spec of product.test_specifications ?? []) {
        if (!byTestTypeId.has(spec.lab_test_type_id)) {
          byTestTypeId.set(spec.lab_test_type_id, {
            labTestTypeId: spec.lab_test_type_id,
            testName: spec.test_name,
            testCategory: spec.test_category,
            specification: spec.specification,
          })
        }
      }
    }

    return Array.from(byTestTypeId.values()).sort((a, b) => a.testName.localeCompare(b.testName))
  }, [successLotWithSpecs])

  const isOrganolepticCategory = useCallback((category: string | null | undefined) => {
    const normalized = (category ?? "").trim().toLowerCase()
    return normalized.includes("organoleptic")
  }, [])

  useEffect(() => {
    if (!isDaanePdfDialogOpen || initializedDaaneSelection) return
    if (isLoadingSuccessLotWithSpecs) return
    if (isSuccessLotWithSpecsError) return

    const defaultSelected = daaneTestSelectionOptions
      .filter((option) => !isOrganolepticCategory(option.testCategory))
      .map((option) => option.labTestTypeId)

    setSelectedDaaneTestIds(defaultSelected)
    setInitializedDaaneSelection(true)
  }, [
    isDaanePdfDialogOpen,
    initializedDaaneSelection,
    daaneTestSelectionOptions,
    isLoadingSuccessLotWithSpecs,
    isSuccessLotWithSpecsError,
    isOrganolepticCategory,
  ])

  const onSubmit = async (formData: SampleForm) => {
    console.log('=== onSubmit called ===', formData)
    try {
      if (formData.lot_type === "parent_lot") {
        // Validate product selection
        if (selectedProducts.length === 0) {
          setParentProductTouched(true)
          return
        }

        // For parent_lot: Create lot then create sublots
        const validSubBatches = subBatches.filter(sb => sb.batch_number.trim() !== '')
        if (validSubBatches.length === 0) {
          alert("Please add at least one sub-batch")
          return
        }

        // Calculate earliest mfg date from sub-batches
        const earliestMfgDate = validSubBatches.reduce((min, sb) =>
          sb.mfg_date < min ? sb.mfg_date : min, validSubBatches[0].mfg_date)

        // Use the computed exp date (includes nudge days)
        const calculatedExpDate = parentLotExpDate || calculateExpiryDate(earliestMfgDate, selectedProducts[0].product.expiry_duration_months, expiryNudgeDays)

        const lot = await createMutation.mutateAsync({
          lot_number: formData.lot_number,
          lot_type: "parent_lot" as LotType,
          mfg_date: earliestMfgDate,
          exp_date: calculatedExpDate,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: selectedProducts.map((sp) => ({
            product_id: sp.product.id,
            percentage: sp.percentage,
          })),
        })

        // Create sublots
        await createSublotsMutation.mutateAsync({
          lotId: lot.id,
          sublots: validSubBatches.map(sb => ({
            sublot_number: `${formData.lot_number}-${sb.batch_number}`,
            production_date: sb.mfg_date,
          })),
        })

        // Show success dialog
        const product = selectedProducts[0]?.product
        setSuccessData({
          lotId: lot.id,
          referenceNumber: lot.reference_number,
          brand: product?.brand || '',
          productName: product?.product_name || '',
          flavorSize: product ? formatFlavorSize(product) : null,
          lotNumber: formData.lot_number,
          lotType: 'Parent Lot',
        })
      } else if (formData.lot_type === "multi_sku_composite") {
        // For multi_sku_composite: Use composite products grid data

        // Check if there are any rows
        if (compositeProducts.length === 0) {
          alert("Please add at least one product row")
          return
        }

        // Check for products without valid product_id
        const invalidProducts = compositeProducts.filter(cp => cp.product_id === null)
        if (invalidProducts.length > 0) {
          alert("Please select valid products from the database for all rows. Hover over invalid entries to see the error.")
          return
        }

        // Check for products without batch numbers
        const productsWithoutBatch = compositeProducts.filter(cp => cp.batch_number.trim() === '')
        if (productsWithoutBatch.length > 0) {
          alert("Please enter batch numbers for all products")
          return
        }

        const validProducts = compositeProducts.filter(cp => cp.product_id !== null && cp.batch_number.trim() !== '')

        // Generate composite lot number from batch numbers
        const compositeLotNumber = "COMP-" + validProducts.map(p => p.batch_number).join("-")

        // Calculate equal percentages for all products
        const equalPercentage = 100 / validProducts.length

        // Calculate earliest mfg date
        const earliestMfgDate = validProducts.reduce((min, cp) =>
          cp.mfg_date < min ? cp.mfg_date : min, validProducts[0].mfg_date)

        // Calculate exp_date using shortest expiry among products
        const minExpiry = validProducts.reduce((min, cp) => {
          const product = productsData?.items.find(p => p.id === cp.product_id)
          return product ? Math.min(min, product.expiry_duration_months) : min
        }, Infinity)
        const calculatedExpDate = minExpiry !== Infinity
          ? calculateExpiryDate(earliestMfgDate, minExpiry, expiryNudgeDays)
          : undefined

        const compositeLot = await createMutation.mutateAsync({
          lot_number: compositeLotNumber,
          lot_type: "multi_sku_composite" as LotType,
          mfg_date: earliestMfgDate,
          exp_date: calculatedExpDate,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: validProducts.map((cp) => ({
            product_id: cp.product_id!,
            percentage: equalPercentage,
          })),
        })

        // Show success dialog - for composite, show product count with line breaks
        const productNames = validProducts.map(cp => cp.product_name).join('\n')
        setSuccessData({
          lotId: compositeLot.id,
          referenceNumber: compositeLot.reference_number,
          brand: `${validProducts.length} Products`,
          productName: productNames,
          flavorSize: null,
          lotNumber: compositeLotNumber,
          lotType: 'Multi-SKU Composite',
        })
      } else {
        // STANDARD lot - use original logic

        // Validate product selection
        if (selectedProducts.length === 0) {
          setStandardProductTouched(true)
          return
        }

        const payload = {
          lot_number: formData.lot_number,
          lot_type: formData.lot_type as LotType,
          mfg_date: formData.mfg_date || undefined,
          exp_date: formData.exp_date || undefined,
          reference_number: formData.reference_number || undefined,
          generate_coa: formData.generate_coa,
          products: selectedProducts.map((sp) => ({
            product_id: sp.product.id,
            percentage: sp.percentage,
          })),
        }
        console.log('=== STANDARD lot payload ===', JSON.stringify(payload, null, 2))
        const standardLot = await createMutation.mutateAsync(payload)
        console.log('=== Mutation succeeded ===')

        // Show success dialog
        const stdProduct = selectedProducts[0]?.product
        setSuccessData({
          lotId: standardLot.id,
          referenceNumber: standardLot.reference_number,
          brand: stdProduct?.brand || '',
          productName: stdProduct?.product_name || '',
          flavorSize: stdProduct ? formatFlavorSize(stdProduct) : null,
          lotNumber: formData.lot_number,
          lotType: 'Standard',
        })
      }
    } catch (error: any) {
      console.error('=== Submit error ===', error)
      // Log the actual validation error from the backend
      if (error?.response?.data) {
        console.error('=== Backend validation error ===', JSON.stringify(error.response.data, null, 2))
      }
      if (error?.response?.data?.detail) {
        // FastAPI validation errors
        alert(`Validation error: ${JSON.stringify(error.response.data.detail)}`)
      }
    }
  }

  const handleDownloadCoc = async () => {
    if (!successData) return
    try {
      const result = await downloadCocMutation.mutateAsync(successData.lotId)
      toast.success("Daane COC (XLSX) downloaded")
      if (result.limitExceeded) {
        toast.warning(`Daane COC supports ${result.testLimit} tests. ${result.testCount} tests found; only the first ${result.testLimit} were included.`)
      }
    } catch (error) {
      console.error("Failed to download Daane COC:", error)
      toast.error("Failed to download Daane COC")
    }
  }

  const handleDownloadCocPdf = async () => {
    if (!successData) return
    if (selectedDaaneTestIds.length === 0) {
      toast.error("Select at least one test to generate the Daane COC PDF")
      return
    }
    try {
      const result = await downloadCocPdfMutation.mutateAsync({
        lotId: successData.lotId,
        selectedLabTestTypeIds: selectedDaaneTestIds,
        specialInstructions: daaneSpecialInstructions,
      })
      toast.success("Daane COC (PDF) downloaded")
      if (result.limitExceeded) {
        toast.warning(`Daane COC supports ${result.testLimit} tests. ${result.testCount} tests found; only the first ${result.testLimit} were included.`)
      }
      setIsDaanePdfDialogOpen(false)
    } catch (error) {
      console.error("Failed to download Daane COC PDF:", error)
      toast.error("Failed to download Daane COC PDF")
    }
  }

  const handleOpenDaanePdfDialog = () => {
    if (!successData) return
    if (isSuccessLotWithSpecsError) {
      void refetchSuccessLotWithSpecs()
    }
    setInitializedDaaneSelection(false)
    setSelectedDaaneTestIds([])

    // Auto-populate special instructions from product serving sizes
    const servingSizes = [
      ...new Set(
        (successLotWithSpecs?.products ?? [])
          .map((p) => p.serving_size)
          .filter(Boolean) as string[]
      ),
    ]
    if (servingSizes.length > 0) {
      setDaaneSpecialInstructions(`Serving Size = ${servingSizes.sort().join(", ")}`)
    } else {
      setDaaneSpecialInstructions("(NO SERVING SIZE DETERMINED)")
    }

    setIsDaanePdfDialogOpen(true)
  }

  const toggleDaaneTestSelection = (labTestTypeId: number) => {
    setSelectedDaaneTestIds((prev) =>
      prev.includes(labTestTypeId)
        ? prev.filter((id) => id !== labTestTypeId)
        : [...prev, labTestTypeId]
    )
  }

  const addProduct = (product: Product) => {
    if (!selectedProducts.find((sp) => sp.product.id === product.id)) {
      setSelectedProducts([...selectedProducts, { product }])
    }
    setIsProductDialogOpen(false)
    setProductSearch("")
  }

  // removeProduct reserved for future use (e.g., removing products from selected list)
  void ((productId: number) => {
    setSelectedProducts(selectedProducts.filter((sp) => sp.product.id !== productId))
  })

  const filteredProducts = productsData?.items.filter(
    (p) =>
      p.display_name.toLowerCase().includes(productSearch.toLowerCase()) ||
      p.brand.toLowerCase().includes(productSearch.toLowerCase())
  )

  // Sub-batch grid handlers
  const addSubBatch = useCallback(() => {
    setSubBatches(prev => [
      ...prev,
      {
        id: nextSubBatchId,
        mfg_date: watchedMfgDate || new Date().toISOString().split('T')[0],
        batch_number: ''
      }
    ])
    setNextSubBatchId(prev => prev + 1)
  }, [nextSubBatchId, watchedMfgDate])

  const removeSubBatch = useCallback((id: number) => {
    setSubBatches(prev => prev.filter(sb => sb.id !== id))
  }, [])

  // Composite products grid handlers
  const addCompositeProduct = useCallback(() => {
    setCompositeProducts(prev => [
      ...prev,
      { id: nextCompositeId, product_id: null, product_name: '', mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }
    ])
    setNextCompositeId(prev => prev + 1)
  }, [nextCompositeId])

  const removeCompositeProduct = useCallback((id: number) => {
    setCompositeProducts(prev => prev.filter(cp => cp.id !== id))
  }, [])

  // TanStack Table columns for Composite Products
  const compositeColumnHelper = createColumnHelper<CompositeProductRow>()
  const compositeColumns = useMemo(() => [
    compositeColumnHelper.accessor('product_name', {
      header: 'Product',
      size: 350,
      cell: (info) => {
        const rowId = info.row.original.id
        const currentProduct = info.row.original

        return (
          <ProductAutocomplete
            value={currentProduct}
            products={productsData?.items || []}
            isLoading={isProductsLoading}
            onSelect={(product) => {
              setCompositeProducts(prev =>
                prev.map(cp => cp.id === rowId
                  ? { ...cp, product_id: product.id, product_name: product.display_name }
                  : cp
                )
              )
              showSpecPreview(product)
            }}
            onChange={(text) => {
              // Clear product_id when user starts typing (always editable)
              setCompositeProducts(prev =>
                prev.map(cp => cp.id === rowId
                  ? { ...cp, product_id: null, product_name: text }
                  : cp
                )
              )
            }}
            error={!currentProduct.product_id && currentProduct.product_name.trim() !== ''}
            onNextCell={() => {
              // Move to mfg_date column
              setEditingCompositeCell({ rowId, columnId: 'mfg_date' })
            }}
            onPrevCell={() => {
              // Shift+Tab: Go to previous row's batch_number or let browser handle if first row
              const currentRowIndex = compositeProducts.findIndex(cp => cp.id === rowId)
              if (currentRowIndex > 0) {
                const prevRowId = compositeProducts[currentRowIndex - 1].id
                setEditingCompositeCell({ rowId: prevRowId, columnId: 'batch_number' })
              }
              // If first row, don't prevent default - let browser handle natural tab order
            }}
            onNoProductsEnter={() => setShowAddProductDialog(true)}
          />
        )
      },
    }),
    compositeColumnHelper.accessor('mfg_date', {
      header: 'Mfg Date',
      size: 104,
      cell: (info) => {
        const rowId = info.row.original.id
        const isEditing = editingCompositeCell?.rowId === rowId && editingCompositeCell?.columnId === 'mfg_date'

        if (isEditing) {
          return (
            <input
              type="date"
              value={info.getValue()}
              onChange={(e) => {
                setCompositeProducts(prev =>
                  prev.map(cp => cp.id === rowId ? { ...cp, mfg_date: e.target.value } : cp)
                )
              }}
              onBlur={() => setEditingCompositeCell(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  setEditingCompositeCell(null)
                } else if (e.key === 'Tab' && e.shiftKey) {
                  e.preventDefault()
                  // Shift+Tab: Focus product input in same row
                  setEditingCompositeCell(null)
                  const tableEl = (e.target as HTMLElement).closest('table')
                  const rows = tableEl?.querySelectorAll('tbody tr')
                  const currentRowIndex = compositeProducts.findIndex(cp => cp.id === rowId)
                  const currentRow = rows?.[currentRowIndex]
                  requestAnimationFrame(() => {
                    const productInput = currentRow?.querySelector('input[type="text"]') as HTMLInputElement
                    productInput?.focus()
                  })
                } else if (e.key === 'Tab' && !e.shiftKey) {
                  e.preventDefault()
                  setEditingCompositeCell({ rowId, columnId: 'batch_number' })
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500
                [&::-webkit-calendar-picker-indicator]:h-3 [&::-webkit-calendar-picker-indicator]:w-3 [&::-webkit-calendar-picker-indicator]:cursor-pointer"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingCompositeCell({ rowId, columnId: 'mfg_date' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm flex items-center gap-2"
          >
            <span>{info.getValue()}</span>
            <svg className="h-3 w-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )
      },
    }),
    compositeColumnHelper.accessor('batch_number', {
      header: 'Batch #',
      size: 150,
      cell: (info) => {
        const rowId = info.row.original.id
        const isEditing = editingCompositeCell?.rowId === rowId && editingCompositeCell?.columnId === 'batch_number'

        if (isEditing) {
          return (
            <input
              type="text"
              value={info.getValue()}
              onChange={(e) => {
                setCompositeProducts(prev =>
                  prev.map(cp => cp.id === rowId ? { ...cp, batch_number: e.target.value } : cp)
                )
              }}
              onBlur={() => setEditingCompositeCell(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  // Enter closes editing and moves to next section
                  setEditingCompositeCell(null)
                  // Focus next section's first input (exp date nudge)
                  setTimeout(() => {
                    const form = (e.target as HTMLElement).closest('form')
                    const nextSection = form?.querySelector('[data-section="lab-reference"]')
                    const firstFocusable = nextSection?.querySelector('button, input') as HTMLElement
                    firstFocusable?.focus()
                  }, 0)
                } else if (e.key === 'Tab' && e.shiftKey) {
                  e.preventDefault()
                  // Shift+Tab: Go back to mfg_date in same row
                  setEditingCompositeCell({ rowId, columnId: 'mfg_date' })
                } else if (e.key === 'Tab' && !e.shiftKey) {
                  e.preventDefault()
                  setEditingCompositeCell(null)

                  const currentRowIndex = compositeProducts.findIndex(cp => cp.id === rowId)
                  const isLastRow = currentRowIndex === compositeProducts.length - 1
                  const tableEl = (e.target as HTMLElement).closest('table')

                  if (isLastRow) {
                    // Add new row (spreadsheet convention)
                    const newRow = {
                      id: nextCompositeId,
                      product_id: null,
                      product_name: '',
                      mfg_date: new Date().toISOString().split('T')[0],
                      batch_number: ''
                    }
                    setCompositeProducts(prev => [...prev, newRow])
                    setNextCompositeId(prev => prev + 1)
                  }

                  // Focus next row's product input after React renders
                  requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                      const rows = tableEl?.querySelectorAll('tbody tr')
                      const nextRow = rows?.[currentRowIndex + 1]
                      const productInput = nextRow?.querySelector('input[type="text"]') as HTMLInputElement
                      productInput?.focus()
                    })
                  })
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingCompositeCell({ rowId, columnId: 'batch_number' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm"
          >
            {info.getValue() || <span className="text-slate-400 italic text-xs">Click to edit...</span>}
          </div>
        )
      },
    }),
    compositeColumnHelper.display({
      id: 'actions',
      header: '',
      cell: (info) => (
        <button
          onClick={() => removeCompositeProduct(info.row.original.id)}
          className="text-slate-400 hover:text-red-600 transition-colors p-1"
          type="button"
          tabIndex={-1}
          title="Delete row"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
      size: 35,
    }),
  ], [editingCompositeCell, productsData, removeCompositeProduct])

  // TanStack Table instance for Composite Products
  const compositeTable = useReactTable({
    data: compositeProducts,
    columns: compositeColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id.toString(),
  })

  // TanStack Table columns for Sub-Batches (parent_lot)
  const subBatchColumnHelper = createColumnHelper<SubBatchRow>()
  const subBatchColumns = useMemo(() => [
    subBatchColumnHelper.accessor('batch_number', {
      header: 'Batch #',
      size: 200,
      cell: (info) => {
        const rowId = info.row.original.id
        const isEditing = editingSubBatchCell?.rowId === rowId && editingSubBatchCell?.columnId === 'batch_number'

        if (isEditing) {
          return (
            <input
              type="text"
              value={info.getValue()}
              onChange={(e) => {
                setSubBatches(prev =>
                  prev.map(sb => sb.id === rowId ? { ...sb, batch_number: e.target.value } : sb)
                )
              }}
              onBlur={() => setEditingSubBatchCell(null)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  setEditingSubBatchCell(null)
                } else if (e.key === 'Tab' && e.shiftKey) {
                  e.preventDefault()
                  // Shift+Tab: Go to previous row's mfg_date or focus element before table
                  const currentRowIndex = subBatches.findIndex(sb => sb.id === rowId)
                  if (currentRowIndex > 0) {
                    const prevRowId = subBatches[currentRowIndex - 1].id
                    setEditingSubBatchCell({ rowId: prevRowId, columnId: 'mfg_date' })
                  } else {
                    // First row - focus reference number field
                    setEditingSubBatchCell(null)
                    setTimeout(() => {
                      const form = (e.target as HTMLElement).closest('form')
                      const refInput = form?.querySelector('#reference_number') as HTMLElement
                      refInput?.focus()
                    }, 0)
                  }
                } else if (e.key === 'Tab' && !e.shiftKey) {
                  e.preventDefault()
                  // Tab to mfg_date in same row
                  setEditingSubBatchCell({ rowId, columnId: 'mfg_date' })
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingSubBatchCell({ rowId, columnId: 'batch_number' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm"
          >
            {info.getValue() || <span className="text-slate-400 italic text-xs">Click to edit...</span>}
          </div>
        )
      },
    }),
    subBatchColumnHelper.accessor('mfg_date', {
      header: 'Mfg Date',
      size: 104,
      cell: (info) => {
        const rowId = info.row.original.id
        const isEditing = editingSubBatchCell?.rowId === rowId && editingSubBatchCell?.columnId === 'mfg_date'

        if (isEditing) {
          return (
            <input
              type="date"
              value={info.getValue()}
              onChange={(e) => {
                setSubBatches(prev =>
                  prev.map(sb => sb.id === rowId ? { ...sb, mfg_date: e.target.value } : sb)
                )
              }}
              onBlur={() => setEditingSubBatchCell(null)}
              onKeyDown={(e) => {
                const currentDate = new Date(info.getValue())

                if (e.key === 't' || e.key === 'T') {
                  e.preventDefault()
                  const today = new Date().toISOString().split('T')[0]
                  setSubBatches(prev => prev.map(sb => sb.id === rowId ? { ...sb, mfg_date: today } : sb))
                } else if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
                  e.preventDefault()
                  currentDate.setDate(currentDate.getDate() + 1)
                  setSubBatches(prev => prev.map(sb => sb.id === rowId ? { ...sb, mfg_date: currentDate.toISOString().split('T')[0] } : sb))
                } else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
                  e.preventDefault()
                  currentDate.setDate(currentDate.getDate() - 1)
                  setSubBatches(prev => prev.map(sb => sb.id === rowId ? { ...sb, mfg_date: currentDate.toISOString().split('T')[0] } : sb))
                } else if (e.key === 'Enter') {
                  e.preventDefault()
                  // Enter closes editing and moves to submit button
                  setEditingSubBatchCell(null)
                  setTimeout(() => {
                    const form = (e.target as HTMLElement).closest('form')
                    const submitBtn = form?.querySelector('button[type="submit"]') as HTMLElement
                    submitBtn?.focus()
                  }, 0)
                } else if (e.key === 'Tab' && e.shiftKey) {
                  e.preventDefault()
                  // Shift+Tab: Go back to batch_number in same row
                  setEditingSubBatchCell({ rowId, columnId: 'batch_number' })
                } else if (e.key === 'Tab' && !e.shiftKey) {
                  e.preventDefault()

                  const currentRowIndex = subBatches.findIndex(sb => sb.id === rowId)
                  const isLastRow = currentRowIndex === subBatches.length - 1

                  if (isLastRow) {
                    // Add new row and focus it
                    const newRowId = nextSubBatchId
                    const newRow = {
                      id: newRowId,
                      mfg_date: watchedMfgDate || new Date().toISOString().split('T')[0],
                      batch_number: ''
                    }
                    setSubBatches(prev => [...prev, newRow])
                    setNextSubBatchId(prev => prev + 1)
                    // Focus the new row's batch_number
                    setEditingSubBatchCell({ rowId: newRowId, columnId: 'batch_number' })
                  } else {
                    // Focus next existing row's batch_number
                    const nextRowId = subBatches[currentRowIndex + 1].id
                    setEditingSubBatchCell({ rowId: nextRowId, columnId: 'batch_number' })
                  }
                }
              }}
              autoFocus
              className="w-full px-2 py-0.5 text-sm border border-blue-500 rounded focus:outline-none focus:ring-1 focus:ring-blue-500
                [&::-webkit-calendar-picker-indicator]:h-3 [&::-webkit-calendar-picker-indicator]:w-3 [&::-webkit-calendar-picker-indicator]:cursor-pointer"
            />
          )
        }

        return (
          <div
            onClick={() => setEditingSubBatchCell({ rowId, columnId: 'mfg_date' })}
            className="px-2 py-0.5 cursor-pointer hover:bg-slate-50 rounded text-sm flex items-center gap-2"
          >
            <span>{info.getValue()}</span>
            <svg className="h-3 w-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )
      },
    }),
    subBatchColumnHelper.display({
      id: 'actions',
      header: '',
      size: 35,
      cell: (info) => (
        <button
          onClick={() => removeSubBatch(info.row.original.id)}
          className="text-slate-400 hover:text-red-600 transition-colors p-1"
          type="button"
          tabIndex={-1}
          title="Delete row"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      ),
    }),
  ], [editingSubBatchCell, subBatches, nextSubBatchId, watchedMfgDate])

  const subBatchTable = useReactTable({
    data: subBatches,
    columns: subBatchColumns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id.toString(),
  })

  return (
    <div className="mx-auto max-w-7xl p-6 bg-slate-50/40 min-h-screen">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.275 }}
        className="space-y-6 max-w-3xl"
      >
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Create Sample</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Submit a new lot for lab testing
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Lot Type Selection */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5 text-slate-500" />
              <h2 className="font-semibold text-slate-800 text-[15px]">Lot Type</h2>
            </div>
            <p className="mt-1 text-[13px] text-slate-500">
              Select the type of lot you're creating
            </p>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {LOT_TYPES.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setValue("lot_type", type.value)}
                  className={`p-4 border-2 rounded-xl text-left transition-all duration-200 ${
                    watchedLotType === type.value
                      ? "border-slate-900 bg-slate-50 shadow-sm"
                      : "border-slate-200/80 hover:border-slate-300 hover:bg-slate-50/50"
                  }`}
                >
                  <p className="font-semibold text-slate-900 text-[14px]">{type.label}</p>
                  <p className="text-[12px] text-slate-500 mt-1">
                    {type.description}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* STANDARD: Combined Product + Lot Details */}
        {watchedLotType === "standard" && (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
              <div className="flex items-center gap-2">
                <Beaker className="h-5 w-5 text-slate-500" />
                <h2 className="font-semibold text-slate-800 text-[15px]">Lot Details</h2>
              </div>
            </div>
            <div className="p-6 space-y-4">
              {/* Product Autocomplete */}
              {(() => {
                const hasValidProduct = selectedProducts.length > 0
                const hasText = standardProductText.trim().length > 0
                const showError = standardProductTouched && !hasValidProduct && hasText
                // isInvalid reserved for future accessibility use
                void (standardProductTouched && !hasValidProduct)

                return (
                  <div className="space-y-1.5">
                    <Label className="text-[13px] font-semibold text-slate-700">Product *</Label>
                    <div className={`flex h-10 w-full rounded-md border px-3 py-2 text-sm ring-offset-white focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 ${
                      hasValidProduct ? 'bg-white' : 'bg-slate-50'
                    } ${
                      showError
                        ? 'border-red-500 ring-2 ring-red-500/20 focus-within:ring-red-500'
                        : 'border-slate-200 focus-within:ring-slate-950'
                    }`}>
                      <ProductAutocomplete
                        value={{
                          product_id: selectedProducts[0]?.product.id ?? null,
                          product_name: selectedProducts[0]?.product.display_name ?? standardProductText
                        }}
                        products={productsData?.items || []}
                        isLoading={isProductsLoading}
                        onSelect={(product) => {
                          setSelectedProducts([{ product }])
                          setStandardProductText(product.display_name)
                          showSpecPreview(product)
                        }}
                        onChange={(text) => {
                          setStandardProductText(text)
                          // Only clear selection if text no longer matches current product
                          if (selectedProducts.length > 0 && text !== selectedProducts[0].product.display_name) {
                            setSelectedProducts([])
                          }
                        }}
                        onBlur={() => setStandardProductTouched(true)}
                        onNoProductsEnter={() => setShowAddProductDialog(true)}
                      />
                    </div>
                    {showError ? (
                      <p className="text-[11px] text-red-600">
                        Select a valid product from the list
                      </p>
                    ) : selectedProducts.length > 0 ? (
                      <p className="text-[11px] text-slate-500">
                        {selectedProducts[0].product.brand} • Expires {selectedProducts[0].product.expiry_duration_months} months from mfg
                      </p>
                    ) : null}
                  </div>
                )
              })()}

              {/* Lot Number + Dates */}
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="lot_number" className="text-[13px] font-semibold text-slate-700">Lot Number *</Label>
                  <Input
                    id="lot_number"
                    {...register("lot_number")}
                    placeholder="e.g., ABC123"
                    aria-invalid={!!errors.lot_number}
                    className="border-slate-200 h-10"
                  />
                  {errors.lot_number && (
                    <p className="text-[13px] text-red-600">{errors.lot_number.message}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="mfg_date" className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
                    <CalendarDays className="h-4 w-4" />
                    Mfg Date
                  </Label>
                  <Input
                    id="mfg_date"
                    type="date"
                    {...register("mfg_date")}
                    className="border-slate-200 h-10"
                    onKeyDown={(e) => {
                      if (e.key === 't' || e.key === 'T') {
                        e.preventDefault()
                        setValue("mfg_date", new Date().toISOString().split('T')[0])
                      }
                    }}
                  />
                  <p className="text-[11px] text-slate-500">
                    Press "T" for today
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="exp_date" className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
                    <CalendarDays className="h-4 w-4" />
                    Exp Date
                  </Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="exp_date"
                      type="date"
                      {...register("exp_date")}
                      className="border-slate-200 h-10 bg-slate-50 flex-1"
                      readOnly
                    />
                    <div
                      className="flex items-center border border-slate-200 rounded-lg bg-white h-10"
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
                          e.preventDefault()
                          setExpiryNudgeDays(prev => prev - 1)
                        } else if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
                          e.preventDefault()
                          setExpiryNudgeDays(prev => prev + 1)
                        }
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setExpiryNudgeDays(prev => prev - 1)}
                        className="px-2 h-full hover:bg-slate-100 rounded-l-lg transition-colors text-slate-400 hover:text-slate-600"
                        title="-1 day (↓/←)"
                      >
                        <ChevronDown className="h-4 w-4" />
                      </button>
                      <span className="px-1 text-[11px] text-slate-500 min-w-[28px] text-center">
                        {expiryNudgeDays === 0 ? '0d' : `${expiryNudgeDays > 0 ? '+' : ''}${expiryNudgeDays}d`}
                      </span>
                      <button
                        type="button"
                        onClick={() => setExpiryNudgeDays(prev => prev + 1)}
                        className="px-2 h-full hover:bg-slate-100 rounded-r-lg transition-colors text-slate-400 hover:text-slate-600"
                        title="+1 day (↑/→)"
                      >
                        <ChevronUp className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Auto-calculated
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Lab Reference # Autogeneration - separate block */}
        {watchedLotType === "standard" && (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-slate-500" />
                <h2 className="font-semibold text-slate-800 text-[15px]">Lab Reference #</h2>
              </div>
              <p className="mt-1 text-[13px] text-slate-500">
                Auto-generated as YYMMDD-XXX unless specified
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="reference_number" className="text-[13px] font-semibold text-slate-700">Lab Reference #</Label>
                  <Input
                    id="reference_number"
                    {...register("reference_number")}
                    placeholder="Auto-generated if empty"
                    className="border-slate-200 h-10 !bg-slate-200"
                  />
                </div>
                <div className="flex items-end pb-1">
                  <div className="flex items-center gap-2.5">
                    <input
                      id="generate_coa"
                      type="checkbox"
                      {...register("generate_coa")}
                      className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
                    />
                    <Label htmlFor="generate_coa" className="font-normal text-[14px] text-slate-700">
                      Generate COA when approved
                    </Label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* parent_lot: Parent Lot Details + Sub-Batches */}
        {watchedLotType === "parent_lot" && (
          <>
            {/* Parent Lot Details */}
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
                <div className="flex items-center gap-2">
                  <Beaker className="h-5 w-5 text-slate-500" />
                  <h2 className="font-semibold text-slate-800 text-[15px]">Parent Lot Details</h2>
                </div>
              </div>
              <div className="p-6 space-y-4">
                {/* Product Autocomplete */}
                {(() => {
                  const hasValidProduct = selectedProducts.length > 0
                  const hasText = parentProductText.trim().length > 0
                  const showError = parentProductTouched && !hasValidProduct && hasText

                  return (
                    <div className="space-y-1.5">
                      <Label className="text-[13px] font-semibold text-slate-700">Product *</Label>
                      <div className={`flex h-10 w-full rounded-md border px-3 py-2 text-sm ring-offset-white focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 ${
                        hasValidProduct ? 'bg-white' : 'bg-slate-50'
                      } ${
                        showError
                          ? 'border-red-500 ring-2 ring-red-500/20 focus-within:ring-red-500'
                          : 'border-slate-200 focus-within:ring-slate-950'
                      }`}>
                        <ProductAutocomplete
                          value={{
                            product_id: selectedProducts[0]?.product.id ?? null,
                            product_name: selectedProducts[0]?.product.display_name ?? parentProductText
                          }}
                          products={productsData?.items || []}
                          isLoading={isProductsLoading}
                          onSelect={(product) => {
                            setSelectedProducts([{ product }])
                            setParentProductText(product.display_name)
                            showSpecPreview(product)
                          }}
                          onChange={(text) => {
                            setParentProductText(text)
                            if (selectedProducts.length > 0 && text !== selectedProducts[0].product.display_name) {
                              setSelectedProducts([])
                            }
                          }}
                          onBlur={() => setParentProductTouched(true)}
                          onNoProductsEnter={() => setShowAddProductDialog(true)}
                        />
                      </div>
                      {showError ? (
                        <p className="text-[11px] text-red-600">
                          Select a valid product from the list
                        </p>
                      ) : selectedProducts.length > 0 ? (
                        <p className="text-[11px] text-slate-500">
                          {selectedProducts[0].product.brand} • Expires {selectedProducts[0].product.expiry_duration_months} months from mfg
                        </p>
                      ) : null}
                    </div>
                  )
                })()}

                {/* Master Lot # + Exp Date */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="lot_number" className="text-[13px] font-semibold text-slate-700">Master Lot # *</Label>
                    <Input
                      id="lot_number"
                      {...register("lot_number")}
                      placeholder="e.g., BATCH-2024-001"
                      aria-invalid={!!errors.lot_number}
                      className="border-slate-200 h-10"
                    />
                    {errors.lot_number && (
                      <p className="text-[13px] text-red-600">{errors.lot_number.message}</p>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <Label className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
                      <CalendarDays className="h-4 w-4" />
                      Exp Date
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        type="date"
                        value={parentLotExpDate}
                        className="border-slate-200 h-10 bg-slate-50 flex-1"
                        readOnly
                      />
                      <div
                        className="flex items-center border border-slate-200 rounded-lg bg-white h-10"
                        onKeyDown={(e) => {
                          if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
                            e.preventDefault()
                            setExpiryNudgeDays(prev => prev - 1)
                          } else if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
                            e.preventDefault()
                            setExpiryNudgeDays(prev => prev + 1)
                          }
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setExpiryNudgeDays(prev => prev - 1)}
                          className="px-2 h-full hover:bg-slate-100 rounded-l-lg transition-colors text-slate-400 hover:text-slate-600"
                          title="-1 day (↓/←)"
                        >
                          <ChevronDown className="h-4 w-4" />
                        </button>
                        <span className="px-1 text-[11px] text-slate-500 min-w-[28px] text-center">
                          {expiryNudgeDays === 0 ? '0d' : `${expiryNudgeDays > 0 ? '+' : ''}${expiryNudgeDays}d`}
                        </span>
                        <button
                          type="button"
                          onClick={() => setExpiryNudgeDays(prev => prev + 1)}
                          className="px-2 h-full hover:bg-slate-100 rounded-r-lg transition-colors text-slate-400 hover:text-slate-600"
                          title="+1 day (↑/→)"
                        >
                          <ChevronUp className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      Auto-calculated from earliest sub-batch mfg date
                    </p>
                  </div>
                </div>

                {/* Lab Reference # + Generate COA */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="reference_number" className="text-[13px] font-semibold text-slate-700">
                      Lab Reference # <span className="font-normal text-slate-400">(auto-generated)</span>
                    </Label>
                    <Input
                      id="reference_number"
                      {...register("reference_number")}
                      placeholder="Leave blank to auto-generate"
                      className="border-slate-200 h-10 !bg-slate-200"
                    />
                  </div>
                  <div className="flex items-end pb-1">
                    <div className="flex items-center gap-2.5">
                      <input
                        id="generate_coa_parent"
                        type="checkbox"
                        {...register("generate_coa")}
                        className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
                      />
                      <Label htmlFor="generate_coa_parent" className="font-normal text-[14px] text-slate-700">
                        Generate COA when approved
                      </Label>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Sub-Batches Grid */}
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold text-slate-900 text-[15px]">Sub-Batches</h2>
                    <p className="mt-1 text-[13px] text-slate-500">
                      Add sub-batch details (one COA will be generated for the master lot)
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addSubBatch}
                    className="border-slate-200 h-9"
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Add Row
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
                  <thead>
                    <tr className="border-b border-slate-200 bg-slate-50">
                      {subBatchTable.getHeaderGroups().map((headerGroup) =>
                        headerGroup.headers.map((header) => (
                          <th
                            key={header.id}
                            style={{ width: header.getSize() }}
                            className="text-left font-semibold text-slate-700 text-xs tracking-wide px-3 py-2 uppercase"
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                          </th>
                        ))
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {subBatchTable.getRowModel().rows.map((row) => (
                      <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} style={{ width: cell.column.getSize() }} className="px-3 py-1.5">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* multi_sku_composite: Composite Products Grid */}
        {watchedLotType === "multi_sku_composite" && (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900 text-[15px]">Composite Batch Details</h2>
                  <p className="mt-1 text-[13px] text-slate-500">
                    Add products with their batch numbers (a COA will be generated for each item)
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addCompositeProduct}
                  className="border-slate-200 h-9"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Row
                </Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {compositeTable.getHeaderGroups().map((headerGroup) =>
                      headerGroup.headers.map((header) => (
                        <th
                          key={header.id}
                          style={{ width: header.getSize() }}
                          className="text-left font-semibold text-slate-700 text-xs tracking-wide px-3 py-2 uppercase"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))
                    )}
                  </tr>
                </thead>
                <tbody>
                  {compositeTable.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50/50">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} style={{ width: cell.column.getSize() }} className="px-3 py-1.5">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* multi_sku_composite: Lab Reference & Exp Date */}
        {watchedLotType === "multi_sku_composite" && (
          <div data-section="lab-reference" className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="border-b border-slate-200 bg-slate-50/80 px-6 py-4">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-slate-500" />
                <h2 className="font-semibold text-slate-800 text-[15px]">Lab Reference & Expiration</h2>
              </div>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="flex items-center gap-2 text-[13px] font-semibold text-slate-700">
                    <CalendarDays className="h-4 w-4" />
                    Exp Date
                  </Label>
                  <div className="flex items-center gap-2">
                    <Input
                      type="date"
                      {...register("exp_date")}
                      className="border-slate-200 h-10 bg-slate-50 flex-1"
                      readOnly
                    />
                    <div
                      className="flex items-center border border-slate-200 rounded-lg bg-white h-10"
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') {
                          e.preventDefault()
                          setExpiryNudgeDays(prev => prev - 1)
                        } else if (e.key === 'ArrowUp' || e.key === 'ArrowRight') {
                          e.preventDefault()
                          setExpiryNudgeDays(prev => prev + 1)
                        }
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setExpiryNudgeDays(prev => prev - 1)}
                        className="px-2 h-full hover:bg-slate-100 rounded-l-lg transition-colors text-slate-400 hover:text-slate-600"
                        title="-1 day (↓/←)"
                      >
                        <ChevronDown className="h-4 w-4" />
                      </button>
                      <span className="px-1 text-[11px] text-slate-500 min-w-[28px] text-center">
                        {expiryNudgeDays === 0 ? '0d' : `${expiryNudgeDays > 0 ? '+' : ''}${expiryNudgeDays}d`}
                      </span>
                      <button
                        type="button"
                        onClick={() => setExpiryNudgeDays(prev => prev + 1)}
                        className="px-2 h-full hover:bg-slate-100 rounded-r-lg transition-colors text-slate-400 hover:text-slate-600"
                        title="+1 day (↑/→)"
                      >
                        <ChevronUp className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Auto-calculated from shortest product expiry
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="reference_number" className="text-[13px] font-semibold text-slate-700">
                    Lab Reference # <span className="font-normal text-slate-400">(auto-generated)</span>
                  </Label>
                  <Input
                    id="reference_number"
                    {...register("reference_number")}
                    placeholder="Leave blank to auto-generate"
                    className="border-slate-200 h-10 !bg-slate-200"
                  />
                  <div className="flex items-center gap-2.5 pt-0.5">
                    <input
                      id="generate_coa_composite"
                      type="checkbox"
                      {...register("generate_coa")}
                      className="rounded border-slate-300 text-slate-900 focus:ring-slate-500 h-4 w-4"
                    />
                    <Label htmlFor="generate_coa_composite" className="font-normal text-[14px] text-slate-700">
                      Generate COA when approved
                    </Label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/")}
            className="border-slate-200 h-10"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={createMutation.isPending}
            className="bg-slate-900 hover:bg-slate-800 text-white shadow-sm h-10"
          >
            {createMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Sample
          </Button>
        </div>
      </form>

      {/* Product Selection Dialog */}
      <Dialog open={isProductDialogOpen} onOpenChange={setIsProductDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[18px] font-bold text-slate-900">Add Product</DialogTitle>
            <DialogDescription className="text-[14px] text-slate-500">
              Search and select a product to add
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 mt-2">
            <Input
              placeholder="Search products..."
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              autoFocus
              className="border-slate-200 h-11"
            />

            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredProducts?.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => addProduct(product)}
                  disabled={selectedProducts.some((sp) => sp.product.id === product.id)}
                  className="w-full text-left p-3.5 rounded-xl hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-transparent hover:border-slate-200"
                >
                  <p className="font-semibold text-slate-900 text-[14px]">{product.display_name}</p>
                  <p className="text-[12px] text-slate-500 mt-0.5">{product.brand}</p>
                </button>
              ))}
              {filteredProducts?.length === 0 && (
                <p className="text-center text-[14px] text-slate-500 py-6">
                  No products found
                </p>
              )}
            </div>
          </div>

          <DialogFooter className="pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsProductDialogOpen(false)}
              className="border-slate-200 h-10"
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Success Dialog */}
      <Dialog
        open={!!successData}
        onOpenChange={(open) => {
          if (!open) {
            setSuccessData(null)
            setIsDaanePdfDialogOpen(false)
            setInitializedDaaneSelection(false)
            setSelectedDaaneTestIds([])
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-green-600 flex items-center gap-2 text-[18px]">
              <CheckCircle2 className="h-5 w-5" />
              Sample Created Successfully
            </DialogTitle>
          </DialogHeader>

          <div className="py-4 space-y-5">
            {/* Reference number */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Lot Reference</p>
                <p className="text-2xl font-mono font-bold text-slate-900">
                  {successData?.referenceNumber}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-slate-200"
                onClick={() => {
                  navigator.clipboard.writeText(successData?.referenceNumber || '')
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }}
              >
                {copied ? (
                  <Check className="h-4 w-4 mr-2 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4 mr-2 text-slate-500" />
                )}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>

            {/* Details */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500 mb-2">Product</p>
                <p className="font-medium text-slate-900">{successData?.brand}</p>
                <p className="text-slate-700 text-sm whitespace-pre-line">{successData?.productName}</p>
                {successData?.flavorSize && (
                  <p className="text-slate-600 text-sm">{successData.flavorSize}</p>
                )}
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Lot Number</span>
                  <span className="font-medium text-slate-900">{successData?.lotNumber}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Type</span>
                  <span className="font-medium text-slate-900">{successData?.lotType}</span>
                </div>
              </div>
            </div>

            {/* Downloads */}
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-3">Daane COC</p>
              <div className="flex flex-col sm:flex-row gap-2">
                <Button
                  variant="outline"
                  className="border-slate-200 w-full sm:w-auto"
                  onClick={handleDownloadCoc}
                  disabled={downloadCocMutation.isPending}
                >
                  {downloadCocMutation.isPending ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-2" />
                  )}
                  Download XLSX
                </Button>
                <Button
                  variant="outline"
                  className="border-slate-200 w-full sm:w-auto"
                  onClick={handleOpenDaanePdfDialog}
                  disabled={isLoadingSuccessLotWithSpecs}
                >
                  {isLoadingSuccessLotWithSpecs ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-2" />
                  )}
                  Generate Daane COC (PDF)
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter className="flex-col sm:flex-row sm:justify-end gap-2">
            <Button
              variant="outline"
              className="border-slate-200 w-full sm:w-auto"
              onClick={() => {
                setSuccessData(null)
                setCopied(false)
                setIsDaanePdfDialogOpen(false)
                setSelectedDaaneTestIds([])
                setInitializedDaaneSelection(false)
                form.reset()
                setSelectedProducts([])
                setStandardProductText('')
                setParentProductText('')
                setSubBatches([{ id: 1, mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }])
                setNextSubBatchId(2)
                setCompositeProducts([{ id: 1, product_id: null, product_name: '', mfg_date: new Date().toISOString().split('T')[0], batch_number: '' }])
                setNextCompositeId(2)
                setExpiryNudgeDays(0)
              }}
            >
              Create Another
            </Button>
            <Button
              className="bg-slate-900 hover:bg-slate-800 text-white w-full sm:w-auto"
              onClick={() => navigate(`/tracker?highlight=${successData?.referenceNumber}`)}
            >
              View in Tracker
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Main Lot Daane PDF selection dialog */}
      <Dialog
        open={isDaanePdfDialogOpen}
        onOpenChange={(open) => {
          setIsDaanePdfDialogOpen(open)
          if (!open) {
            setInitializedDaaneSelection(false)
            setSelectedDaaneTestIds([])
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-[18px] text-slate-900">Generate Daane COC (PDF)</DialogTitle>
            <DialogDescription>
              Select which tests to include. Organoleptic tests are unchecked by default.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            <div>
              <Label className="text-sm font-medium text-slate-700 mb-1.5 block">
                Special Instructions
              </Label>
              <Textarea
                value={daaneSpecialInstructions}
                onChange={(e) => setDaaneSpecialInstructions(e.target.value)}
                placeholder="e.g., Serving Size = 30g"
                className="min-h-[60px] resize-none text-sm"
              />
            </div>
            <div className="border rounded-lg overflow-hidden max-h-[360px] overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50">
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Test</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Specification</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoadingSuccessLotWithSpecs ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-slate-500 py-8">
                        Loading tests...
                      </TableCell>
                    </TableRow>
                  ) : isSuccessLotWithSpecsError ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-amber-700 py-8">
                        Failed to load tests for this sample.
                        <Button
                          variant="link"
                          className="h-auto p-0 ml-2 text-amber-700"
                          onClick={() => {
                            void refetchSuccessLotWithSpecs()
                          }}
                        >
                          Retry
                        </Button>
                      </TableCell>
                    </TableRow>
                  ) : daaneTestSelectionOptions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-slate-500 py-8">
                        No tests available for this sample
                      </TableCell>
                    </TableRow>
                  ) : (
                    daaneTestSelectionOptions.map((test) => {
                      const isSelected = selectedDaaneTestIds.includes(test.labTestTypeId)
                      return (
                        <TableRow
                          key={test.labTestTypeId}
                          className={`cursor-pointer ${isSelected ? "bg-emerald-50/60" : ""}`}
                          onClick={() => toggleDaaneTestSelection(test.labTestTypeId)}
                        >
                          <TableCell onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                              checked={isSelected}
                              onCheckedChange={() => toggleDaaneTestSelection(test.labTestTypeId)}
                            />
                          </TableCell>
                          <TableCell className="font-medium text-slate-900">{test.testName}</TableCell>
                          <TableCell className="text-slate-600">{test.testCategory || "-"}</TableCell>
                          <TableCell className="text-slate-600">{test.specification || "-"}</TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </div>
            <p className="text-xs text-slate-500">
              {selectedDaaneTestIds.length} test{selectedDaaneTestIds.length !== 1 ? "s" : ""} selected
            </p>
            {selectedDaaneTestIds.length === 0 && (
              <p className="text-xs text-amber-600">Select at least one test to generate the Daane COC PDF.</p>
            )}
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button
              variant="outline"
              className="border-slate-200 w-full sm:w-auto"
              onClick={() => setIsDaanePdfDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              className="bg-slate-900 hover:bg-slate-800 text-white w-full sm:w-auto"
              onClick={handleDownloadCocPdf}
              disabled={
                downloadCocPdfMutation.isPending ||
                isSuccessLotWithSpecsError ||
                selectedDaaneTestIds.length === 0 ||
                daaneTestSelectionOptions.length === 0
              }
            >
              {downloadCocPdfMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Generate PDF
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add New Product Dialog */}
      <Dialog open={showAddProductDialog} onOpenChange={setShowAddProductDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-slate-900 text-[18px]">Product Not Found</DialogTitle>
            <DialogDescription className="text-slate-500">
              No matching product was found in your catalog. Would you like to add a new product?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowAddProductDialog(false)}
              className="border-slate-200"
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="bg-slate-900 hover:bg-slate-800 text-white"
              onClick={() => {
                setShowAddProductDialog(false)
                navigate('/products?addNew=true')
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add New Product
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </motion.div>

      <SpecPreviewPanel
        product={specPreviewProduct}
        onDismiss={() => setSpecPreviewProduct(null)}
        onChangeSpecs={(id) => window.open(`/products?editSpecs=${id}`, '_blank')}
      />
    </div>
  )
}
