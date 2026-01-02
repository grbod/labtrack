import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  productsApi,
  type ProductFilters,
  type CreateProductData,
  type UpdateProductData,
  type CreateTestSpecData,
  type UpdateTestSpecData,
  type BulkImportProductRow,
} from "@/api/products"

export const productKeys = {
  all: ["products"] as const,
  lists: () => [...productKeys.all, "list"] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all, "detail"] as const,
  detail: (id: number) => [...productKeys.details(), id] as const,
  brands: () => [...productKeys.all, "brands"] as const,
  testSpecs: (productId: number) => [...productKeys.all, "testSpecs", productId] as const,
}

export function useProducts(filters: ProductFilters = {}) {
  return useQuery({
    queryKey: productKeys.list(filters),
    queryFn: () => productsApi.list(filters),
  })
}

export function useProduct(id: number) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productsApi.get(id),
    enabled: !!id,
  })
}

export function useBrands() {
  return useQuery({
    queryKey: productKeys.brands(),
    queryFn: () => productsApi.getBrands(),
  })
}

export function useCreateProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateProductData) => productsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.brands() })
    },
  })
}

export function useUpdateProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateProductData }) =>
      productsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.id) })
    },
  })
}

export function useDeleteProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => productsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
    },
  })
}

// Test Specification hooks
export function useProductWithSpecs(id: number) {
  return useQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productsApi.getWithSpecs(id),
    enabled: !!id,
  })
}

export function useProductTestSpecs(productId: number) {
  return useQuery({
    queryKey: productKeys.testSpecs(productId),
    queryFn: () => productsApi.listTestSpecs(productId),
    enabled: !!productId,
  })
}

export function useCreateTestSpec() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, data }: { productId: number; data: CreateTestSpecData }) =>
      productsApi.createTestSpec(productId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.testSpecs(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useUpdateTestSpec() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, specId, data }: { productId: number; specId: number; data: UpdateTestSpecData }) =>
      productsApi.updateTestSpec(productId, specId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.testSpecs(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useDeleteTestSpec() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ productId, specId }: { productId: number; specId: number }) =>
      productsApi.deleteTestSpec(productId, specId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: productKeys.testSpecs(variables.productId) })
      queryClient.invalidateQueries({ queryKey: productKeys.detail(variables.productId) })
    },
  })
}

export function useBulkImportProducts() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (rows: BulkImportProductRow[]) => productsApi.bulkImport(rows),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productKeys.brands() })
    },
  })
}
