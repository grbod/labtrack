import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { usersApi, type UserUpdate, type UserCreateData } from "@/api/users"
import { authApi } from "@/api/client"
import { extractApiErrorMessage } from "@/lib/api-utils"

// Query keys
export const userKeys = {
  all: ["users"] as const,
  list: () => [...userKeys.all, "list"] as const,
  detail: (id: number) => [...userKeys.all, "detail", id] as const,
}

/**
 * Hook to list all users (admin only).
 */
export function useUsers() {
  return useQuery({
    queryKey: userKeys.list(),
    queryFn: usersApi.list,
  })
}

/**
 * Hook to get a single user by ID (admin only).
 */
export function useUser(id: number) {
  return useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => usersApi.get(id),
    enabled: !!id,
  })
}

/**
 * Hook to update a user (admin only).
 */
export function useUpdateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) =>
      usersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.all })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to update user"))
    },
  })
}

/**
 * Hook to create a new user (admin only).
 */
export function useCreateUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: UserCreateData) => usersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.list() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to create user"))
    },
  })
}

/**
 * Hook to delete a user (admin only).
 */
export function useDeleteUser() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => usersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.list() })
    },
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to delete user"))
    },
  })
}

/**
 * Hook to change the current user's password.
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: ({ currentPassword, newPassword }: { currentPassword: string; newPassword: string }) =>
      authApi.changePassword(currentPassword, newPassword),
    onError: (error: unknown) => {
      toast.error(extractApiErrorMessage(error, "Failed to change password"))
    },
  })
}
