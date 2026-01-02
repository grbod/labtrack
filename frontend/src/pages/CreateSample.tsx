import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Plus, Loader2, Package, Beaker, X, CalendarDays } from "lucide-react"
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

import { useProducts } from "@/hooks/useProducts"
import { useCreateLot, useLots } from "@/hooks/useLots"
import type { Product, LotType } from "@/types"

const LOT_TYPES: { value: LotType; label: string; description: string }[] = [
  {
    value: "STANDARD",
    label: "Standard Lot",
    description: "Single product, single lot",
  },
  {
    value: "PARENT_LOT",
    label: "Parent Lot",
    description: "Master lot with sublots",
  },
  {
    value: "MULTI_SKU_COMPOSITE",
    label: "Multi-SKU Composite",
    description: "Multiple products combined",
  },
]

const sampleSchema = z.object({
  lot_number: z.string().min(1, "Lot number is required"),
  lot_type: z.enum(["STANDARD", "PARENT_LOT", "MULTI_SKU_COMPOSITE"]),
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

export function CreateSamplePage() {
  const navigate = useNavigate()
  const [isProductDialogOpen, setIsProductDialogOpen] = useState(false)
  const [selectedProducts, setSelectedProducts] = useState<SelectedProduct[]>([])
  const [productSearch, setProductSearch] = useState("")

  const { data: productsData } = useProducts({ page_size: 100, is_active: true })
  const { data: lotsData } = useLots({ page: 1, page_size: 10 })
  const createMutation = useCreateLot()

  const form = useForm<SampleForm>({
    resolver: zodResolver(sampleSchema),
    defaultValues: {
      lot_type: "STANDARD",
      generate_coa: true,
    },
  })

  const { register, handleSubmit, watch, setValue, formState: { errors } } = form
  const watchedLotType = watch("lot_type")

  const onSubmit = async (formData: SampleForm) => {
    try {
      await createMutation.mutateAsync({
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
      })
      // Navigate to the lot list or show success
      navigate("/")
    } catch {
      // Error handled by mutation
    }
  }

  const addProduct = (product: Product) => {
    if (!selectedProducts.find((sp) => sp.product.id === product.id)) {
      setSelectedProducts([...selectedProducts, { product }])
    }
    setIsProductDialogOpen(false)
    setProductSearch("")
  }

  const removeProduct = (productId: number) => {
    setSelectedProducts(selectedProducts.filter((sp) => sp.product.id !== productId))
  }

  const updatePercentage = (productId: number, percentage: number | undefined) => {
    setSelectedProducts(
      selectedProducts.map((sp) =>
        sp.product.id === productId ? { ...sp, percentage } : sp
      )
    )
  }

  const filteredProducts = productsData?.items.filter(
    (p) =>
      p.display_name.toLowerCase().includes(productSearch.toLowerCase()) ||
      p.brand.toLowerCase().includes(productSearch.toLowerCase())
  )

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Create Sample</h1>
        <p className="text-muted-foreground text-sm">
          Submit a new lot for lab testing
        </p>
      </div>

      {/* Recent Lots Summary */}
      {lotsData && lotsData.items.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recent Submissions
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-3">
            <div className="flex gap-2 flex-wrap">
              {lotsData.items.slice(0, 5).map((lot) => (
                <span
                  key={lot.id}
                  className="px-2 py-1 bg-muted rounded text-xs font-mono"
                >
                  {lot.reference_number}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Lot Type Selection */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Lot Type
            </CardTitle>
            <CardDescription>
              Select the type of lot you're creating
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {LOT_TYPES.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => setValue("lot_type", type.value as LotType)}
                  className={`p-4 border rounded-lg text-left transition-colors ${
                    watchedLotType === type.value
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  }`}
                >
                  <p className="font-medium">{type.label}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {type.description}
                  </p>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Lot Details */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Beaker className="h-5 w-5" />
              Lot Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="lot_number">Lot Number *</Label>
                <Input
                  id="lot_number"
                  {...register("lot_number")}
                  placeholder="e.g., ABC123"
                  aria-invalid={!!errors.lot_number}
                />
                {errors.lot_number && (
                  <p className="text-sm text-destructive">{errors.lot_number.message}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="reference_number">Reference Number</Label>
                <Input
                  id="reference_number"
                  {...register("reference_number")}
                  placeholder="Auto-generated if empty"
                />
                <p className="text-xs text-muted-foreground">
                  Leave blank to auto-generate (YYMMDD-XXX)
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="mfg_date" className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4" />
                  Manufacturing Date
                </Label>
                <Input
                  id="mfg_date"
                  type="date"
                  {...register("mfg_date")}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="exp_date" className="flex items-center gap-2">
                  <CalendarDays className="h-4 w-4" />
                  Expiration Date
                </Label>
                <Input
                  id="exp_date"
                  type="date"
                  {...register("exp_date")}
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input
                id="generate_coa"
                type="checkbox"
                {...register("generate_coa")}
                className="rounded border-gray-300"
              />
              <Label htmlFor="generate_coa" className="font-normal">
                Generate COA when approved
              </Label>
            </div>
          </CardContent>
        </Card>

        {/* Product Association */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Products</CardTitle>
                <CardDescription>
                  {watchedLotType === "MULTI_SKU_COMPOSITE"
                    ? "Add products and their percentages"
                    : "Associate a product with this lot"}
                </CardDescription>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsProductDialogOpen(true)}
              >
                <Plus className="mr-2 h-4 w-4" />
                Add Product
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {selectedProducts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Package className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No products added yet</p>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  onClick={() => setIsProductDialogOpen(true)}
                >
                  Add a product
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                {selectedProducts.map((sp) => (
                  <div
                    key={sp.product.id}
                    className="flex items-center gap-3 p-3 border rounded-lg"
                  >
                    <div className="flex-1">
                      <p className="font-medium">{sp.product.display_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {sp.product.brand}
                      </p>
                    </div>
                    {watchedLotType === "MULTI_SKU_COMPOSITE" && (
                      <div className="flex items-center gap-2">
                        <Input
                          type="number"
                          min="0"
                          max="100"
                          step="0.01"
                          className="w-20"
                          placeholder="%"
                          value={sp.percentage ?? ""}
                          onChange={(e) =>
                            updatePercentage(
                              sp.product.id,
                              e.target.value ? parseFloat(e.target.value) : undefined
                            )
                          }
                        />
                        <span className="text-sm text-muted-foreground">%</span>
                      </div>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => removeProduct(sp.product.id)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
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
          <Button type="submit" disabled={createMutation.isPending}>
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
            <DialogTitle>Add Product</DialogTitle>
            <DialogDescription>
              Search and select a product to add
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Input
              placeholder="Search products..."
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              autoFocus
            />

            <div className="max-h-[300px] overflow-y-auto space-y-1">
              {filteredProducts?.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => addProduct(product)}
                  disabled={selectedProducts.some((sp) => sp.product.id === product.id)}
                  className="w-full text-left p-2 rounded hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <p className="font-medium">{product.display_name}</p>
                  <p className="text-xs text-muted-foreground">{product.brand}</p>
                </button>
              ))}
              {filteredProducts?.length === 0 && (
                <p className="text-center text-muted-foreground py-4">
                  No products found
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsProductDialogOpen(false)}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
