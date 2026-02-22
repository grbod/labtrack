import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  customersApi,
  type CustomerFilters,
  type CreateCustomerData,
  type UpdateCustomerData,
} from "@/api/customers"
import { extractApiErrorMessage } from "@/lib/api-utils"

export const customerKeys = {
  all: ["customers"] as const,
  lists: () => [...customerKeys.all, "list"] as const,
  list: (filters: CustomerFilters) => [...customerKeys.lists(), filters] as const,
  details: () => [...customerKeys.all, "detail"] as const,
  detail: (id: number) => [...customerKeys.details(), id] as const,
}

export function useCustomers(filters: CustomerFilters = {}) {
  return useQuery({
    queryKey: customerKeys.list(filters),
    queryFn: () => customersApi.list(filters),
  })
}

export function useCustomer(id: number) {
  return useQuery({
    queryKey: customerKeys.detail(id),
    queryFn: () => customersApi.get(id),
    enabled: !!id,
  })
}

export function useCreateCustomer() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CreateCustomerData) => customersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerKeys.lists() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create customer"))
    },
  })
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateCustomerData }) =>
      customersApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: customerKeys.lists() })
      queryClient.invalidateQueries({ queryKey: customerKeys.detail(variables.id) })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update customer"))
    },
  })
}

export function useDeactivateCustomer() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => customersApi.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: customerKeys.lists() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to deactivate customer"))
    },
  })
}

export function useActivateCustomer() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => customersApi.activate(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: customerKeys.lists() })
      queryClient.invalidateQueries({ queryKey: customerKeys.detail(id) })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to activate customer"))
    },
  })
}
